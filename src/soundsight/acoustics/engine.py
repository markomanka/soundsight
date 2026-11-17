# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
r"""The production acoustic engine, first increment: echoes from one thin rigid plate.

What it computes
----------------
For a convex, planar, rigid plate of zero thickness, a point source and a point
receiver (the same point for a person hearing their own click), the echo is the sum of

* the **specular reflection** (image source), present when the reflection point lies
  on the plate, with weight one half when it lies exactly on an edge; and
* the **first-order diffraction** from every edge, by the Biot-Tolstoy-Medwin (BTM)
  secondary-source formulation, which is exact for a rigid wedge. A thin plate's edges
  are wedges of exterior angle :math:`2\pi`, so :math:`\nu = \pi/\theta_w = 1/2`.

The echo is returned as a set of *arrivals*: each a delay and a real amplitude, so that

.. math::

    H(f) = \sum_k a_k\, e^{-2\pi i f \tau_k}

in the conventions of :mod:`soundsight.acoustics.reference.analytic` (a unit point
source radiates :math:`e^{-ikr}/r`). From the arrivals one gets the frequency response
exactly, or an impulse response at any sample rate (:func:`render`).

Edge diffraction
----------------
For an edge from :math:`z = 0` to :math:`z = L`, with source and receiver at cylindrical
coordinates :math:`(r_S, \theta_S, z_S)` and :math:`(r_R, \theta_R, z_R)` about it,

.. math::

    H_\mathrm{d}(f) = -\frac{\nu}{4\pi} \int_0^L
        \frac{e^{-ik(m + l)}}{m\, l} \sum_{\pm\pm}
        \frac{\sin(\nu\varphi_{\pm\pm})}{\cosh(\nu\eta) - \cos(\nu\varphi_{\pm\pm})}\, dz,

with :math:`m, l` the distances from the edge point to source and receiver,
:math:`\varphi_{\pm\pm} = \pi \pm \theta_S \pm \theta_R` and
:math:`\cosh\eta = (m l + (z - z_S)(z - z_R)) / (r_S r_R)`. The prefactor
:math:`\nu/4\pi` is the one for which the diffracted field exactly cancels the jump of
the specular reflection where the reflection point crosses an edge; a test checks this.

The integrand is sharply peaked where the reflection point is close to the edge, so
quadrature is graded geometrically towards the stationary ("apex") point of each edge
before becoming uniform, with a step small enough to follow the phase at the highest
frequency requested.

What it does not do yet
-----------------------
Second- and higher-order diffraction (waves crossing the plate from edge to edge), more
than one object, occlusion, absorption, rooms and two ears. Each is a separate
increment with its own canonical problem. The validated range is stated in
docs/acoustics/engine.md and enforced by the conformance matrix.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND, ComplexArray

FloatArray = NDArray[np.float64]

#: Wedge index of a thin plate's edge: nu = pi / theta_w with theta_w = 2 pi.
NU_THIN_PLATE = 0.5
#: Relative tolerance for geometric tests (planarity, convexity, on-edge reflection).
GEOMETRY_TOLERANCE = 1e-9
#: Smallest grading step near an apex, relative to the edge length. The diffraction
#: integrand near a reflection boundary is a peak of width proportional to the angular
#: distance from the boundary; this resolves it down to about 1e-8 radians.
_GRADING_START = 1e-10
_GRADING_RATIO = 1.6
#: Gauss-Legendre nodes per quadrature interval.
_GAUSS_NODES, _GAUSS_WEIGHTS = np.polynomial.legendre.leggauss(4)
#: Uniform step is c / (STEPS_PER_PERIOD * f_max): the phase advances at most
#: 2 * 2 pi / STEPS_PER_PERIOD per interval (path length grows at most 2 per unit z).
_STEPS_PER_PERIOD = 16


class GeometryError(ValueError):
    """Raised for plates or positions the engine cannot handle."""


@dataclass(frozen=True)
class Plate:
    """A convex, planar, thin rigid plate given by its vertices in order.

    Parameters
    ----------
    vertices
        Array of shape ``(n, 3)``, in metres, ``n >= 3``, in order around the edge
        (either direction).
    """

    vertices: FloatArray

    def __post_init__(self) -> None:
        """Check planarity and convexity; freeze the vertex array."""
        v = np.array(self.vertices, dtype=np.float64, copy=True)
        if v.ndim != 2 or v.shape[1] != 3 or v.shape[0] < 3:  # noqa: PLR2004
            msg = "a plate needs an (n, 3) array of at least 3 vertices"
            raise GeometryError(msg)
        if not np.all(np.isfinite(v)):
            msg = "plate vertices must be finite"
            raise GeometryError(msg)
        centre = v.mean(axis=0)
        size = float(np.max(np.linalg.norm(v - centre, axis=1)))
        if size <= 0.0:
            msg = "plate is degenerate"
            raise GeometryError(msg)
        # Newell's method gives a robust normal for any planar polygon.
        nxt = np.roll(v, -1, axis=0)
        normal = np.array(
            [
                np.sum((v[:, 1] - nxt[:, 1]) * (v[:, 2] + nxt[:, 2])),
                np.sum((v[:, 2] - nxt[:, 2]) * (v[:, 0] + nxt[:, 0])),
                np.sum((v[:, 0] - nxt[:, 0]) * (v[:, 1] + nxt[:, 1])),
            ]
        )
        area2 = float(np.linalg.norm(normal))
        if area2 <= GEOMETRY_TOLERANCE * size**2:
            msg = "plate is degenerate (zero area)"
            raise GeometryError(msg)
        normal /= area2
        if np.max(np.abs((v - centre) @ normal)) > GEOMETRY_TOLERANCE * size * 1e3:
            msg = "plate vertices are not coplanar"
            raise GeometryError(msg)
        edges = nxt - v
        lengths = np.linalg.norm(edges, axis=1)
        if np.any(lengths <= GEOMETRY_TOLERANCE * size):
            msg = "plate has repeated vertices"
            raise GeometryError(msg)
        turn = np.cross(edges, np.roll(edges, -1, axis=0)) @ normal
        if np.any(turn <= GEOMETRY_TOLERANCE * size**2):
            msg = "plate must be strictly convex, with vertices in order"
            raise GeometryError(msg)
        v.setflags(write=False)
        normal.setflags(write=False)
        object.__setattr__(self, "vertices", v)
        object.__setattr__(self, "_normal", normal)
        object.__setattr__(self, "_size", size)

    @property
    def normal(self) -> FloatArray:
        """Unit normal (right-handed with respect to the vertex order)."""
        return self._normal  # type: ignore[attr-defined, no-any-return]

    @property
    def size(self) -> float:
        """Largest distance from the vertex centroid to a vertex, in metres."""
        return self._size  # type: ignore[attr-defined, no-any-return]

    @classmethod
    def regular(
        cls,
        radius: float,
        n_sides: int,
        centre: ArrayLike = (0.0, 0.0, 0.0),
        normal: ArrayLike = (0.0, 0.0, 1.0),
        *,
        equal_area: bool = True,
    ) -> Plate:
        """Return a regular polygon approximating a disk of the given radius.

        With ``equal_area`` the polygon has the area of the disk, which is the choice
        that matches a disk's echo best at low frequency; otherwise ``radius`` is the
        distance from centre to vertex.
        """
        if not radius > 0.0:
            msg = "radius must be positive"
            raise GeometryError(msg)
        if n_sides < 3:  # noqa: PLR2004
            msg = "a polygon needs at least 3 sides"
            raise GeometryError(msg)
        n = np.asarray(normal, dtype=np.float64)
        n = n / np.linalg.norm(n)
        helper = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])  # noqa: PLR2004
        u = np.cross(n, helper)
        u /= np.linalg.norm(u)
        w = np.cross(n, u)
        r = radius
        if equal_area:
            r = radius * math.sqrt(2.0 * math.pi / (n_sides * math.sin(2.0 * math.pi / n_sides)))
        angles = 2.0 * np.pi * np.arange(n_sides) / n_sides
        pts = np.asarray(centre, dtype=np.float64) + r * (
            np.cos(angles)[:, None] * u + np.sin(angles)[:, None] * w
        )
        return cls(pts)


@dataclass(frozen=True)
class Arrivals:
    """An echo as a list of arrivals: delays in seconds and real amplitudes.

    ``specular`` holds the indices of specular arrivals; all others are diffraction.
    """

    delays: FloatArray
    amplitudes: FloatArray
    specular: tuple[int, ...]

    def frequency_response(self, frequency_hz: ArrayLike) -> ComplexArray:
        r"""Evaluate :math:`H(f) = \sum_k a_k e^{-2\pi i f \tau_k}`."""
        f = np.atleast_1d(np.asarray(frequency_hz, dtype=np.float64))
        out = np.empty(f.shape, dtype=np.complex128)
        # Chunked to bound memory for long arrival lists.
        step = max(1, 2_000_000 // max(1, self.delays.size))
        for start in range(0, f.size, step):
            phase = np.exp(-2j * np.pi * np.outer(f[start : start + step], self.delays))
            out[start : start + step] = phase @ self.amplitudes
        return out


def _point(p: ArrayLike, name: str) -> FloatArray:
    a = np.asarray(p, dtype=np.float64)
    if a.shape != (3,) or not np.all(np.isfinite(a)):
        msg = f"{name} must be a finite 3-vector"
        raise GeometryError(msg)
    return a


def specular_arrival(
    plate: Plate, source: ArrayLike, receiver: ArrayLike, c: float = SPEED_OF_SOUND
) -> tuple[float, float] | None:
    """Return ``(delay, amplitude)`` of the specular reflection, or None if there is none.

    The amplitude is ``1 / R`` with ``R`` the image-source path length, halved when the
    reflection point lies on an edge (within :data:`GEOMETRY_TOLERANCE`).
    """
    s, r = _point(source, "source"), _point(receiver, "receiver")
    n = plate.normal
    p0 = plate.vertices[0]
    ds, dr = float((s - p0) @ n), float((r - p0) @ n)
    tol = GEOMETRY_TOLERANCE * plate.size
    if abs(ds) <= tol or abs(dr) <= tol or ds * dr < 0.0:
        return None  # in the plane of the plate, or on opposite sides: no reflection
    image = s - 2.0 * ds * n
    # Reflection point: where the segment image -> receiver crosses the plane.
    hit = image + (r - image) * (abs(ds) / (abs(ds) + abs(dr)))
    v = plate.vertices
    edges = np.roll(v, -1, axis=0) - v
    inward = np.cross(n, edges)
    inward /= np.linalg.norm(inward, axis=1)[:, None]
    # Signed distance from each edge line, positive inside (vertex order may be either way).
    sign = 1.0 if float(np.cross(edges[0], edges[1]) @ n) > 0.0 else -1.0
    dist = sign * np.einsum("ij,ij->i", hit - v, inward)
    if np.any(dist < -tol):
        return None
    weight = 0.5 if np.any(dist <= tol) else 1.0
    length = float(np.linalg.norm(r - image))
    return length / c, weight / length


def _edge_nodes(length: float, apex: float, step: float) -> tuple[FloatArray, FloatArray]:
    """Quadrature nodes and weights on [0, length], graded towards ``apex``."""
    breaks = [0.0, length]
    if 0.0 < apex < length:
        breaks.append(apex)
    first = _GRADING_START * length
    for side in (-1.0, 1.0):
        end = 0.0 if side < 0 else length
        span = abs(end - min(max(apex, 0.0), length))
        g = first
        while g < span:
            breaks.append(min(max(apex, 0.0), length) + side * g)
            g = min(g * _GRADING_RATIO, g + step)
    b = np.unique(np.clip(np.asarray(breaks), 0.0, length))
    a, z = b[:-1], b[1:]
    half = 0.5 * (z - a)
    mid = 0.5 * (z + a)
    nodes = (mid[:, None] + half[:, None] * _GAUSS_NODES[None, :]).ravel()
    weights = (half[:, None] * _GAUSS_WEIGHTS[None, :]).ravel()
    return nodes, weights


def diffraction_arrivals(
    plate: Plate,
    source: ArrayLike,
    receiver: ArrayLike,
    f_max: float,
    *,
    c: float = SPEED_OF_SOUND,
    nu: float = NU_THIN_PLATE,
) -> tuple[FloatArray, FloatArray]:
    """Return delays and amplitudes of first-order edge diffraction from every edge.

    ``f_max`` is the highest frequency at which the result will be used; it sets the
    quadrature step.
    """
    if not f_max > 0.0:
        msg = "f_max must be positive"
        raise ValueError(msg)
    s, r = _point(source, "source"), _point(receiver, "receiver")
    v = plate.vertices
    n = plate.normal
    centre = v.mean(axis=0)
    step = c / (_STEPS_PER_PERIOD * f_max)
    delays: list[FloatArray] = []
    amplitudes: list[FloatArray] = []
    for i in range(v.shape[0]):
        va, vb = v[i], v[(i + 1) % v.shape[0]]
        length = float(np.linalg.norm(vb - va))
        e = (vb - va) / length
        f_dir = np.cross(n, e)
        if float((centre - va) @ f_dir) < 0.0:
            f_dir = -f_dir  # reference face: the half-plane containing the plate
        g_dir = np.cross(e, f_dir)

        def cyl(
            p: FloatArray,
            va: FloatArray = va,
            e: FloatArray = e,
            f_dir: FloatArray = f_dir,
            g_dir: FloatArray = g_dir,
        ) -> tuple[float, float, float]:
            d = p - va
            x, y = float(d @ f_dir), float(d @ g_dir)
            return math.hypot(x, y), math.atan2(y, x) % (2.0 * math.pi), float(d @ e)

        r_s, th_s, z_s = cyl(s)
        r_r, th_r, z_r = cyl(r)
        if min(r_s, r_r) <= GEOMETRY_TOLERANCE * plate.size:
            msg = "source or receiver lies on the line of an edge"
            raise GeometryError(msg)
        # Apex: the stationary point of m + l along the edge line.
        apex = z_s + (z_r - z_s) * r_s / (r_s + r_r)
        z, w = _edge_nodes(length, apex, step)
        m = np.hypot(r_s, z - z_s)
        ell = np.hypot(r_r, z - z_r)
        # cosh(eta) - 1, written without cancellation: with a = z - z_s, b = z - z_r,
        # m l - (r_s r_r - a b) = (r_s b + r_r a)^2 / (m l + r_s r_r - a b), and the
        # numerator vanishes exactly at the apex.
        a_s, b_r = z - z_s, z - z_r
        q = (r_s * b_r + r_r * a_s) ** 2 / ((m * ell + r_s * r_r - a_s * b_r) * r_s * r_r)
        eta = np.log1p(q + np.sqrt(q * (q + 2.0)))  # acosh(1 + q) without cancellation
        # cosh(nu eta) - cos(nu phi) = 2 sinh^2(nu eta / 2) + 2 sin^2(nu phi / 2): both
        # parts are computed directly, so the denominator stays accurate when both
        # cosh and cos are within rounding of 1 (a receiver close to a reflection
        # boundary).
        hyper = 2.0 * np.sinh(0.5 * nu * eta) ** 2
        beta = np.zeros_like(z)
        for phi in (
            math.pi + th_s + th_r,
            math.pi + th_s - th_r,
            math.pi - th_s + th_r,
            math.pi - th_s - th_r,
        ):
            sn = math.sin(nu * phi)
            if sn == 0.0:
                continue
            den = hyper + 2.0 * math.sin(0.5 * nu * phi) ** 2
            # A zero denominator needs eta = 0 and phi = 0 exactly: the receiver is on
            # the boundary and the node on the apex, where the specular term's half
            # weight already carries the contribution.
            beta += np.divide(sn, den, out=np.zeros_like(den), where=den > 0.0)
        delays.append((m + ell) / c)
        amplitudes.append(-(nu / (4.0 * math.pi)) * beta * w / (m * ell))
    return np.concatenate(delays), np.concatenate(amplitudes)


def plate_echo(
    plate: Plate,
    source: ArrayLike,
    receiver: ArrayLike | None = None,
    *,
    f_max: float,
    c: float = SPEED_OF_SOUND,
) -> Arrivals:
    """Return the echo of ``plate``: specular reflection plus first-order diffraction.

    ``receiver`` defaults to the source position (a listener hearing their own click).
    """
    rec = source if receiver is None else receiver
    d_delay, d_amp = diffraction_arrivals(plate, source, rec, f_max, c=c)
    spec = specular_arrival(plate, source, rec, c)
    if spec is None:
        return Arrivals(d_delay, d_amp, ())
    return Arrivals(np.concatenate(([spec[0]], d_delay)), np.concatenate(([spec[1]], d_amp)), (0,))


def render(
    arrivals: Arrivals, sample_rate: int, n_samples: int, *, half_width: int = 32
) -> FloatArray:
    """Render arrivals as an impulse response at ``sample_rate``.

    Each arrival becomes a fractional-delay impulse: a sinc of ``2 * half_width`` taps
    under a Blackman window, so the result is accurate up to about 0.45 times the sample
    rate. Its discrete-time Fourier transform equals ``arrivals.frequency_response``
    within the passband (a test checks this).
    """
    if sample_rate <= 0 or n_samples <= 0 or half_width < 1:
        msg = "sample_rate, n_samples and half_width must be positive"
        raise ValueError(msg)
    out = np.zeros(n_samples)
    pos = arrivals.delays * sample_rate
    if pos.size and float(pos.min()) < half_width:
        # The filter would reach before time zero and be truncated, silently distorting
        # the response (at 48 kHz: arrivals earlier than 0.67 ms, an 11 cm round trip).
        msg = (
            f"an arrival is within {half_width} samples of the start; the fractional-delay "
            "filter would be truncated (use a higher sample rate or a later time origin)"
        )
        raise ValueError(msg)
    base = np.floor(pos).astype(np.int64)
    offsets = np.arange(-half_width + 1, half_width + 1)
    idx = base[:, None] + offsets[None, :]
    x = idx - pos[:, None]
    window = 0.42 + 0.5 * np.cos(np.pi * x / half_width) + 0.08 * np.cos(2 * np.pi * x / half_width)
    taps = np.sinc(x) * np.where(np.abs(x) < half_width, window, 0.0)
    values = arrivals.amplitudes[:, None] * taps
    keep = (idx >= 0) & (idx < n_samples)
    np.add.at(out, idx[keep], values[keep])
    return out
