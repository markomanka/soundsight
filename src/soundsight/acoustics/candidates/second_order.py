# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
r"""Candidate C1 of EXP-0004: second-order edge diffraction for a thin rigid plate.

The first-order diffracted field of an edge is a line of secondary sources (literature
H1). Second order is that construction applied twice: the field of edge *i*, evaluated
at a point of edge *j*, is diffracted again by edge *j*:

.. math::

    H_2(f) = w \left(\frac{\nu}{4\pi}\right)^{2} \sum_{i \ne j}
        \iint \frac{\beta_i\, \beta_j}{m\, n\, l}\, e^{-ik(m + n + l)}\, dz_i\, dz_j,

with :math:`m` from the source to the point on edge *i*, :math:`n` between the two edge
points and :math:`l` to the receiver. In a thin convex plate every edge lies in the plane
of the plate, so the path between two edges runs along the plate's surface: seen from
either edge, the other edge point lies on its face (:math:`\theta = 0`), where the
diffraction coefficient of a rigid wedge counts the face's reflection as well. The
weight :math:`w` that corrects for counting it at both ends is not taken from the
literature or fitted to reference echoes: it is fixed by requiring that second-order
diffraction exactly cancels the jump that first-order diffraction makes across the
plane of the plate beyond an edge (see tests/acoustics/test_second_order.py).

Where the receiver lies close to the plane of the plate beyond an edge, the integrand
peaks sharply along the path that grazes that edge; quadrature over the second edge is
then graded towards the stationary point for every point of the first edge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from soundsight.acoustics.canonical import Disk, Target, UnsupportedTargetError, Wall
from soundsight.acoustics.engine import (
    _GAUSS_NODES,
    _GAUSS_WEIGHTS,
    _STEPS_PER_PERIOD,
    NU_THIN_PLATE,
    Arrivals,
    GeometryError,
    Plate,
    _edge_nodes,
    _point,
    plate_echo,
)
from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND, ComplexArray, plane_echo

FloatArray = NDArray[np.float64]
Frame = dict[str, FloatArray | float]
#: Smallest distance from an edge line at which a source or receiver is accepted (m).
_ON_EDGE = 1e-12

#: Weight of the second-order term, fixed by the continuity test (not fitted to data):
#: with the coefficients evaluated on the face at both edges, w = 1 cancels the jump of
#: first-order diffraction across the plane of the plate beyond an edge to within
#: 0.06 percent at 0.1 mm from the plane, at every frequency tested.
WEIGHT = 1.0

#: Grade the quadrature on the second edge when the receiver's angle about it is within
#: this many radians of the plane of the plate beyond the edge (theta = pi).
GRAZING_WINDOW = 0.35


def _frames(plate: Plate) -> list[Frame]:
    v, n = plate.vertices, plate.normal
    centre = v.mean(axis=0)
    frames: list[Frame] = []
    for i in range(v.shape[0]):
        va, vb = v[i], v[(i + 1) % v.shape[0]]
        length = float(np.linalg.norm(vb - va))
        e = (vb - va) / length
        f = np.cross(n, e)
        if float((centre - va) @ f) < 0.0:
            f = -f
        frames.append({"va": va, "e": e, "f": f, "g": np.cross(e, f), "length": length})
    return frames


def _cyl(p: FloatArray, fr: Frame) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Cylindrical coordinates (r, theta in [0, 2 pi), z) of points about an edge."""
    d = np.atleast_2d(p) - fr["va"]
    x, y = d @ fr["f"], d @ fr["g"]
    return np.hypot(x, y), np.arctan2(y, x) % (2.0 * math.pi), d @ fr["e"]


def _uniform_nodes(length: float, step: float) -> tuple[FloatArray, FloatArray]:
    n_int = max(1, math.ceil(length / step))
    b = np.linspace(0.0, length, n_int + 1)
    half, mid = 0.5 * np.diff(b), 0.5 * (b[1:] + b[:-1])
    return (
        (mid[:, None] + half[:, None] * _GAUSS_NODES[None, :]).ravel(),
        (half[:, None] * _GAUSS_WEIGHTS[None, :]).ravel(),
    )


def _q(
    r_a: FloatArray,
    r_b: FloatArray,
    *,
    a: FloatArray,
    b: FloatArray,
    d1: FloatArray,
    d2: FloatArray,
) -> FloatArray:
    """cosh(eta) - 1 without cancellation (see the engine's first-order code)."""
    return (r_a * b + r_b * a) ** 2 / ((d1 * d2 + r_a * r_b - a * b) * r_a * r_b)


def _beta_face(eta: FloatArray, theta_other: FloatArray | float, nu: float) -> FloatArray:
    """BTM coefficient with one end on the face (theta = 0): the four terms pair up."""
    hyper = 2.0 * np.sinh(0.5 * nu * eta) ** 2
    out = np.zeros(np.broadcast(eta, theta_other).shape)
    for phi in (math.pi + np.asarray(theta_other), math.pi - np.asarray(theta_other)):
        den = hyper + 2.0 * np.sin(0.5 * nu * phi) ** 2
        out = out + 2.0 * np.divide(np.sin(nu * phi), den, out=np.zeros_like(out), where=den > 0)
    return out


def _eta(q: FloatArray) -> FloatArray:
    q = np.maximum(q, 0.0)
    return np.log1p(q + np.sqrt(q * (q + 2.0)))


@dataclass(frozen=True)
class _Leg:
    """Quadrature points on the first edge and their geometry."""

    points: FloatArray
    z: FloatArray
    weights: FloatArray
    to_source: FloatArray
    z_on_second: FloatArray
    r_from_second: FloatArray


def _pair(
    leg: _Leg,
    second: tuple[FloatArray, FloatArray, Frame, Frame],
    ends: tuple[float, float, float, float, float, float],
    receiver: FloatArray,
    nu: float,
) -> tuple[FloatArray, FloatArray]:
    """Path lengths and amplitudes (before the prefactor) for one block of edge pairs."""
    z2, w2, fi, fj = second
    rs, ths, zs, rr, thr, zr = ends
    p2 = fj["va"] + z2[:, None] * fj["e"]
    r2i, _, z2i = _cyl(p2, fi)  # edge-j points seen from edge i: on its face
    nn = np.linalg.norm(leg.points[:, None, :] - p2[None, :, :], axis=2)
    m = leg.to_source[:, None]
    q1 = _q(
        np.full_like(nn, rs),
        r2i[None, :],
        a=leg.z[:, None] - zs,
        b=leg.z[:, None] - z2i[None, :],
        d1=m,
        d2=nn,
    )
    ell = np.linalg.norm(p2 - receiver, axis=1)[None, :]
    q2 = _q(
        leg.r_from_second[:, None] * np.ones_like(nn),
        np.full_like(nn, rr),
        a=z2[None, :] - leg.z_on_second[:, None],
        b=z2[None, :] - zr,
        d1=nn,
        d2=ell,
    )
    beta = _beta_face(_eta(q1), ths, nu) * _beta_face(_eta(q2), thr, nu)
    amp = beta / (m * nn * ell) * leg.weights[:, None] * w2[None, :]
    return (m + nn + ell).ravel(), amp.ravel()


def second_order_arrivals(
    plate: Plate,
    source: ArrayLike,
    receiver: ArrayLike,
    f_max: float,
    *,
    weight: float = WEIGHT,
    c: float = SPEED_OF_SOUND,
    nu: float = NU_THIN_PLATE,
    receiving_edges: tuple[int, ...] | None = None,
) -> tuple[FloatArray, FloatArray]:
    """Delays and amplitudes of second-order edge diffraction over all ordered edge pairs.

    ``receiving_edges`` restricts the second edge of each pair (for tests).
    """
    if not f_max > 0.0:
        msg = "f_max must be positive"
        raise ValueError(msg)
    s, r = _point(source, "source"), _point(receiver, "receiver")
    frames = _frames(plate)

    # Reciprocity: put the endpoint nearer the plane of the plate on the receiving side,
    # where the quadrature is graded.
    def grazing(p: FloatArray) -> float:
        return min(abs(float(_cyl(p, fr)[1][0]) - math.pi) for fr in frames)

    if receiving_edges is None and grazing(s) < grazing(r):
        s, r = r, s
    step = c / (_STEPS_PER_PERIOD * f_max)
    nodes = []
    for fr in frames:
        z, w = _uniform_nodes(float(fr["length"]), step)
        nodes.append((z, w, fr["va"] + z[:, None] * fr["e"]))
    delays: list[FloatArray] = []
    amps: list[FloatArray] = []
    pref = weight * (nu / (4.0 * math.pi)) ** 2
    for i, fi in enumerate(frames):
        rs, ths, zs = (float(x[0]) for x in _cyl(s, fi))
        if rs <= _ON_EDGE:
            msg = "source lies on the line of an edge"
            raise GeometryError(msg)
        z1, w1, p1 = nodes[i]
        m = np.linalg.norm(p1 - s, axis=1)
        for j, fj in enumerate(frames):
            if i == j or (receiving_edges is not None and j not in receiving_edges):
                continue
            rr, thr, zr = (float(x[0]) for x in _cyl(r, fj))
            if rr <= _ON_EDGE:
                msg = "receiver lies on the line of an edge"
                raise GeometryError(msg)
            r1j, _, z1j = _cyl(p1, fj)  # edge-i points seen from edge j: on its face
            if abs(thr - math.pi) < GRAZING_WINDOW:
                blocks = []
                for k in range(z1.size):
                    apex = z1j[k] + (zr - z1j[k]) * r1j[k] / (r1j[k] + rr)
                    z2, w2 = _edge_nodes(float(fj["length"]), float(apex), step)
                    blocks.append((slice(k, k + 1), z2, w2))
            else:
                blocks = [(slice(None), nodes[j][0], nodes[j][1])]
            for sel, z2, w2 in blocks:
                d, a = _pair(
                    _Leg(p1[sel], z1[sel], w1[sel], m[sel], z1j[sel], r1j[sel]),
                    (z2, w2, fi, fj),
                    (rs, ths, zs, rr, thr, zr),
                    r,
                    nu,
                )
                delays.append(d / c)
                amps.append(pref * a)
    return np.concatenate(delays), np.concatenate(amps)


def plate_echo_second_order(
    plate: Plate,
    source: ArrayLike,
    receiver: ArrayLike | None = None,
    *,
    f_max: float,
    weight: float = WEIGHT,
    c: float = SPEED_OF_SOUND,
) -> Arrivals:
    """Specular reflection, first-order and second-order diffraction."""
    rec = source if receiver is None else receiver
    first = plate_echo(plate, source, rec, f_max=f_max, c=c)
    d2, a2 = second_order_arrivals(plate, source, rec, f_max, weight=weight, c=c)
    return Arrivals(
        np.concatenate((first.delays, d2)), np.concatenate((first.amplitudes, a2)), first.specular
    )


def render_dense(
    arrivals: Arrivals, sample_rate: int, n_samples: int, *, oversample: int = 16
) -> FloatArray:
    """Render a very large number of arrivals as an impulse response.

    Arrivals are spread by linear interpolation onto a grid ``oversample`` times finer,
    the triangle kernel this implies is divided out exactly in the frequency domain, the
    result is low-passed (flat to 0.45, zero above 0.5 times the sample rate) and
    decimated. Cost grows linearly with the number of arrivals, unlike
    :func:`soundsight.acoustics.engine.render`. Aliasing of the interpolation kernel
    limits accuracy to about 1e-3 at 0.45 times the sample rate with the default
    oversampling.
    """
    if sample_rate <= 0 or n_samples <= 0 or oversample < 2:  # noqa: PLR2004
        msg = "sample_rate and n_samples must be positive and oversample at least 2"
        raise ValueError(msg)
    rate = sample_rate * oversample
    n_fine = n_samples * oversample
    pos = arrivals.delays * rate
    idx = np.floor(pos).astype(np.int64)
    frac = pos - idx
    keep = (idx >= 0) & (idx < n_fine - 1)
    grid = np.bincount(
        idx[keep], weights=arrivals.amplitudes[keep] * (1.0 - frac[keep]), minlength=n_fine
    )
    grid += np.bincount(
        idx[keep] + 1, weights=arrivals.amplitudes[keep] * frac[keep], minlength=n_fine
    )
    size = 1 << math.ceil(math.log2(2 * n_fine))
    spectrum = np.fft.rfft(grid[:n_fine], n=size)
    f = np.fft.rfftfreq(size, 1.0 / rate)
    kernel = np.sinc(f / rate) ** 2
    lo, hi = 0.45 * sample_rate, 0.5 * sample_rate
    taper = np.clip((hi - f) / (hi - lo), 0.0, 1.0)
    taper = 0.5 - 0.5 * np.cos(np.pi * taper)
    fine = np.fft.irfft(spectrum * taper / kernel, n=size)[:n_fine]
    return np.asarray(fine[::oversample] * oversample, dtype=np.float64)


@dataclass(frozen=True)
class SecondOrderPlateModel:
    """Candidate C1 on canonical targets: a disk as a regular polygon of equal area."""

    c: float = SPEED_OF_SOUND
    n_sides: int = 96
    name: str = "candidate-c1"

    def echo_ratio(self, target: Target, frequency_hz: ArrayLike) -> ComplexArray:
        """Return the candidate's echo divided by that of a wall at the same distance."""
        f = np.atleast_1d(np.asarray(frequency_hz, dtype=np.float64))
        if isinstance(target, Wall):
            return np.ones(f.shape, dtype=np.complex128)
        if isinstance(target, Disk):
            plate = Plate.regular(target.radius, self.n_sides, centre=(0.0, 0.0, target.distance))
            echo = plate_echo_second_order(plate, (0.0, 0.0, 0.0), f_max=float(f.max()), c=self.c)
            return np.asarray(
                echo.frequency_response(f) / plane_echo(f, target.distance, self.c),
                dtype=np.complex128,
            )
        raise UnsupportedTargetError(f"{self.name} has no model for {type(target).__name__}")
