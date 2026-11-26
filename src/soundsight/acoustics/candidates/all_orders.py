# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
r"""Candidate C2 of EXP-0004: edge diffraction of all orders for a thin rigid plate.

Diffraction of order *n* is a chain source -> edge point -> ... -> edge point ->
receiver, in which every edge point re-radiates what reaches it, weighted by the rigid
wedge coefficient :math:`\beta` of its edge (literature H1). Candidate C1 sums chains of
length two. Here every length is summed at once by solving a linear system for the
*edge-source amplitudes* :math:`X(b \to c)`, the total wave arriving at edge point *c*
from edge point *b* (the formulation of literature H3):

.. math::

    X = X_1 + T X, \qquad
    (T X)(c \to d) = -\frac{\nu}{4\pi}\, \frac{e^{-ik|c-d|}}{|c-d|}\, w_d
                     \sum_b X(b \to c)\, \beta_c(b, d),

where :math:`X_1` holds the waves first diffracted at one edge and arriving at another,
and :math:`w_d` are quadrature weights. The echo is the specular reflection plus
first-order diffraction plus :math:`\sum X(b \to c)\, K(b \to c)`, with *K* the last step
to the receiver. Truncating the series :math:`X = X_1 + T X_1 + \dots` after its first
term gives exactly candidate C1's second order (a test checks this).

The coefficients :math:`\beta_c(b, d)` depend only on geometry: they are computed once
per plate and reused for every frequency. In a convex plate every edge point lies on the
face of every other edge, where the coefficient for a thin plate (:math:`\nu = 1/2`)
takes the closed form :math:`\beta = 4 / \cosh(\eta/2) = 4 / \sqrt{1 + q/2}` with
:math:`q = \cosh\eta - 1`.

Limits of this candidate: source and receiver must not lie close to the plane of the
plate beyond an edge (no graded quadrature for that case, unlike C1); memory grows with
the cube of the number of edge points.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.sparse.linalg import LinearOperator, gmres

from soundsight.acoustics.canonical import Disk, Target, UnsupportedTargetError, Wall
from soundsight.acoustics.engine import (
    _GAUSS_NODES,
    _GAUSS_WEIGHTS,
    NU_THIN_PLATE,
    GeometryError,
    Plate,
    _point,
    plate_echo,
)
from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND, ComplexArray, plane_echo

FloatArray = NDArray[np.float64]

#: Quadrature intervals are at most this fraction of the shortest wavelength.
INTERVAL_PER_WAVELENGTH = 0.5
#: Endpoints closer than this (radians) to the plate's plane beyond an edge are refused.
GRAZING_LIMIT = 0.35
#: Smallest distance from an edge line at which a source or receiver is accepted (m).
_ON_EDGE = 1e-12
#: Relative residual at which the linear solver stops.
SOLVER_TOLERANCE = 1e-9


@dataclass(frozen=True)
class EdgeNodes:
    """Quadrature points on all edges, with the geometry the kernel needs."""

    points: FloatArray  # (N, 3)
    weights: FloatArray  # (N,)
    edge: NDArray[np.int64]  # (N,) edge index of each point
    frames: tuple[tuple[FloatArray, FloatArray, FloatArray, FloatArray], ...]  # va, e, f, g


def edge_nodes(plate: Plate, f_max: float, c: float = SPEED_OF_SOUND) -> EdgeNodes:
    """Gauss-Legendre points on every edge, intervals at most half a wavelength long."""
    if not f_max > 0.0:
        msg = "f_max must be positive"
        raise ValueError(msg)
    v, n = plate.vertices, plate.normal
    centre = v.mean(axis=0)
    step = INTERVAL_PER_WAVELENGTH * c / f_max
    pts, wts, idx, frames = [], [], [], []
    for i in range(v.shape[0]):
        va, vb = v[i], v[(i + 1) % v.shape[0]]
        length = float(np.linalg.norm(vb - va))
        e = (vb - va) / length
        f = np.cross(n, e)
        if float((centre - va) @ f) < 0.0:
            f = -f
        frames.append((va, e, f, np.cross(e, f)))
        k = max(1, math.ceil(length / step))
        b = np.linspace(0.0, length, k + 1)
        half, mid = 0.5 * np.diff(b), 0.5 * (b[1:] + b[:-1])
        z = (mid[:, None] + half[:, None] * _GAUSS_NODES[None, :]).ravel()
        pts.append(va + z[:, None] * e)
        wts.append((half[:, None] * _GAUSS_WEIGHTS[None, :]).ravel())
        idx.append(np.full(z.size, i))
    return EdgeNodes(np.vstack(pts), np.concatenate(wts), np.concatenate(idx), tuple(frames))


def _cyl(points: FloatArray, frame: tuple[FloatArray, ...]) -> tuple[FloatArray, ...]:
    va, e, f, g = frame
    d = np.atleast_2d(points) - va
    x, y = d @ f, d @ g
    return np.hypot(x, y), np.arctan2(y, x) % (2.0 * math.pi), d @ e


def _q(
    r1: FloatArray,
    z1: FloatArray,
    r2: FloatArray,
    z2: FloatArray,
    *,
    zc: FloatArray,
    m: FloatArray,
    ell: FloatArray,
) -> FloatArray:
    """cosh(eta) - 1 at edge coordinate zc, written without cancellation."""
    a, b = zc - z1, zc - z2
    return (r1 * b + r2 * a) ** 2 / ((m * ell + r1 * r2 - a * b) * r1 * r2)


def _beta_face_general(q: FloatArray, theta: float, nu: float) -> FloatArray:
    """Coefficient with one end on the face and the other at angle ``theta``."""
    q = np.maximum(q, 0.0)
    eta = np.log1p(q + np.sqrt(q * (q + 2.0)))
    hyper = 2.0 * np.sinh(0.5 * nu * eta) ** 2
    out = np.zeros_like(q)
    for phi in (math.pi + theta, math.pi - theta):
        out += 2.0 * math.sin(nu * phi) / (hyper + 2.0 * math.sin(0.5 * nu * phi) ** 2)
    return out


@dataclass(frozen=True)
class Kernel:
    """Frequency-independent parts of the edge-source equation for one plate and two endpoints."""

    nodes: EdgeNodes
    beta: FloatArray  # (N_c, N_b, N_d): beta_c(b, d), zero where b or d is on c's edge
    beta_source: FloatArray  # (N_c, N_d): beta_c(source, d)
    beta_receiver: FloatArray  # (N_c, N_b): beta_c(b, receiver)
    distance: FloatArray  # (N, N) between edge points; inf on the same edge
    to_source: FloatArray  # (N,)
    to_receiver: FloatArray  # (N,)
    nu: float


def build_kernel(
    plate: Plate,
    source: ArrayLike,
    receiver: ArrayLike,
    f_max: float,
    *,
    c: float = SPEED_OF_SOUND,
    nu: float = NU_THIN_PLATE,
) -> Kernel:
    """Compute every geometric coefficient of the equation once."""
    s, r = _point(source, "source"), _point(receiver, "receiver")
    nodes = edge_nodes(plate, f_max, c)
    p, n = nodes.points, nodes.points.shape[0]
    dist = np.linalg.norm(p[:, None, :] - p[None, :, :], axis=2)
    same = nodes.edge[:, None] == nodes.edge[None, :]
    dist[same] = np.inf
    to_s, to_r = np.linalg.norm(p - s, axis=1), np.linalg.norm(p - r, axis=1)
    beta = np.zeros((n, n, n))
    beta_s = np.zeros((n, n))
    beta_r = np.zeros((n, n))
    for i, frame in enumerate(nodes.frames):
        cs = np.flatnonzero(nodes.edge == i)
        other = ~(nodes.edge == i)
        rr, _, zz = _cyl(p, frame)  # all points about edge i (on its face if other)
        rs, ths, zs = (float(x[0]) for x in _cyl(s, frame))
        rq, thr, zr = (float(x[0]) for x in _cyl(r, frame))
        for name, th in (("source", ths), ("receiver", thr)):
            if min(rs, rq) <= _ON_EDGE or abs(th - math.pi) < GRAZING_LIMIT:
                msg = f"{name} is on an edge line or close to the plate's plane beyond an edge"
                raise GeometryError(msg)
        ro, zo = rr[other], zz[other]
        for c_idx in cs:
            zc = zz[c_idx]
            m_b = dist[other, c_idx]  # from each b to c
            # b -> c -> d, both b and d on the face: beta = 4 / sqrt(1 + q / 2)
            q = _q(
                ro[:, None],
                zo[:, None],
                ro[None, :],
                zo[None, :],
                zc=zc,
                m=m_b[:, None],
                ell=m_b[None, :],
            )
            block = 4.0 / np.sqrt(1.0 + 0.5 * np.maximum(q, 0.0))
            beta[c_idx][np.ix_(other, other)] = block
            qs = _q(
                np.full(ro.shape, rs),
                np.full(ro.shape, zs),
                ro,
                zo,
                zc=zc,
                m=np.full(ro.shape, to_s[c_idx]),
                ell=m_b,
            )
            beta_s[c_idx, other] = _beta_face_general(qs, ths, nu)
            qr = _q(
                ro,
                zo,
                np.full(ro.shape, rq),
                np.full(ro.shape, zr),
                zc=zc,
                m=m_b,
                ell=np.full(ro.shape, to_r[c_idx]),
            )
            beta_r[c_idx, other] = _beta_face_general(qr, thr, nu)
    return Kernel(nodes, beta, beta_s, beta_r, dist, to_s, to_r, nu)


def higher_order_response(
    kernel: Kernel, frequency_hz: float, *, c: float = SPEED_OF_SOUND, max_order: int | None = None
) -> complex:
    """Diffraction of order 2 and above at one frequency (all orders unless ``max_order``)."""
    k = 2.0 * math.pi * frequency_hz / c
    a = -kernel.nu / (4.0 * math.pi)
    w = kernel.nodes.weights
    finite = np.isfinite(kernel.distance)  # pairs on the same edge do not interact
    safe = np.where(finite, kernel.distance, 1.0)
    g = np.where(finite, np.exp(-1j * k * safe) / safe, 0.0)
    g_s = np.exp(-1j * k * kernel.to_source) / kernel.to_source
    g_r = np.exp(-1j * k * kernel.to_receiver) / kernel.to_receiver
    step = a * g * w[None, :]  # step[c, d]: propagation c -> d with quadrature weight
    # X1[c, d]: first diffracted at c (from the source), arriving at d.
    x1: ComplexArray = np.asarray(
        (g_s * w)[:, None] * kernel.beta_source * step, dtype=np.complex128
    )
    final = a * kernel.beta_receiver * g_r[:, None]  # final[c, b]: from b via c to receiver

    def transfer(x: ComplexArray) -> ComplexArray:
        # (T X)[c, d] = step[c, d] * sum_b X[b, c] beta[c, b, d]
        xt = x.T
        mixed = np.einsum("cb,cbd->cd", xt.real, kernel.beta) + 1j * np.einsum(
            "cb,cbd->cd", xt.imag, kernel.beta
        )
        return np.asarray(step * mixed, dtype=np.complex128)

    def response(x: ComplexArray) -> complex:
        # sum over states (b -> c) of X[b, c] * final[c, b]
        return complex(np.sum(x * final.T))

    if max_order is not None:
        if max_order < 2:  # noqa: PLR2004
            msg = "max_order must be at least 2"
            raise ValueError(msg)
        total, term = 0j, x1
        for _ in range(max_order - 1):
            total += response(term)
            term = transfer(term)
        return total
    n = x1.shape[0]
    op = LinearOperator(
        (n * n, n * n), matvec=lambda v: v - transfer(v.reshape(n, n)).ravel(), dtype=complex
    )
    sol, info = gmres(op, x1.ravel(), rtol=SOLVER_TOLERANCE, atol=0.0, restart=60, maxiter=40)
    if info != 0:
        msg = f"edge-source equation did not converge at {frequency_hz} Hz"
        raise ArithmeticError(msg)
    return response(sol.reshape(n, n))


def echo_all_orders(
    plate: Plate,
    source: ArrayLike,
    receiver: ArrayLike | None,
    frequency_hz: ArrayLike,
    *,
    c: float = SPEED_OF_SOUND,
    max_order: int | None = None,
) -> ComplexArray:
    """Specular reflection plus edge diffraction of all orders, at each frequency."""
    rec = source if receiver is None else receiver
    f = np.atleast_1d(np.asarray(frequency_hz, dtype=np.float64))
    first = plate_echo(plate, source, rec, f_max=float(f.max()), c=c).frequency_response(f)
    kernel = build_kernel(plate, source, rec, float(f.max()), c=c)
    higher = np.array([higher_order_response(kernel, fi, c=c, max_order=max_order) for fi in f])
    return np.asarray(first + higher, dtype=np.complex128)


class BudgetExceededError(RuntimeError):
    """Raised when a computation exceeds its time budget; records how far it got."""

    def __init__(self, budget_s: float, done: int, total: int) -> None:
        """Store the budget and the progress made before stopping."""
        super().__init__(f"stopped after {budget_s} s with {done} of {total} frequencies done")
        self.budget_s, self.done, self.total = budget_s, done, total


def impulse_response(
    plate: Plate,
    source: ArrayLike,
    receiver: ArrayLike | None,
    sample_rate: int,
    n_samples: int,
    *,
    c: float = SPEED_OF_SOUND,
    budget_s: float | None = None,
) -> FloatArray:
    """Impulse response with diffraction of all orders, from the frequency response.

    Specular reflection and first-order diffraction are rendered in the time domain by
    the engine; higher orders are solved at every FFT frequency up to the Nyquist
    frequency (kernels are rebuilt per octave so that the number of edge points follows
    the wavelength) and added by inverse FFT. With ``budget_s`` the computation stops
    with :class:`BudgetExceededError` as soon as the elapsed time exceeds it.
    """
    import time  # noqa: PLC0415

    from soundsight.acoustics.engine import render  # noqa: PLC0415

    started = time.perf_counter()
    rec = source if receiver is None else receiver
    first = render(
        plate_echo(plate, source, rec, f_max=sample_rate / 2, c=c), sample_rate, n_samples
    )
    f = np.fft.rfftfreq(n_samples, 1.0 / sample_rate)
    higher = np.zeros(f.size, dtype=np.complex128)
    todo = np.flatnonzero((f > 0.0) & (f <= 0.45 * sample_rate))
    top = 0.45 * sample_rate
    edges = [top / 2**k for k in range(8, -1, -1)]
    done = 0
    lower = 0.0
    for upper in edges:
        band = todo[(f[todo] > lower) & (f[todo] <= upper)]
        lower = upper
        if band.size == 0:
            continue
        kernel = build_kernel(plate, source, rec, upper, c=c)
        for i in band:
            if budget_s is not None and time.perf_counter() - started > budget_s:
                raise BudgetExceededError(budget_s, done, todo.size)
            higher[i] = higher_order_response(kernel, f[i], c=c)
            done += 1
    return np.asarray(first + np.fft.irfft(higher, n=n_samples), dtype=np.float64)


@dataclass(frozen=True)
class AllOrdersPlateModel:
    """Candidate C2 on canonical targets: a disk as a regular polygon of equal area."""

    c: float = SPEED_OF_SOUND
    n_sides: int = 48
    name: str = "candidate-c2"

    def echo_ratio(self, target: Target, frequency_hz: ArrayLike) -> ComplexArray:
        """Return the candidate's echo divided by that of a wall at the same distance."""
        f = np.atleast_1d(np.asarray(frequency_hz, dtype=np.float64))
        if isinstance(target, Wall):
            return np.ones(f.shape, dtype=np.complex128)
        if isinstance(target, Disk):
            plate = Plate.regular(target.radius, self.n_sides, centre=(0.0, 0.0, target.distance))
            echo = echo_all_orders(plate, (0.0, 0.0, 0.0), None, f, c=self.c)
            return np.asarray(echo / plane_echo(f, target.distance, self.c), dtype=np.complex128)
        raise UnsupportedTargetError(f"{self.name} has no model for {type(target).__name__}")


def higher_order_responses(
    plate: Plate,
    source: ArrayLike,
    receiver: ArrayLike | None,
    frequency_hz: ArrayLike,
    *,
    c: float = SPEED_OF_SOUND,
    cache: dict[float, complex] | None = None,
    deadline: float | None = None,
) -> ComplexArray:
    """Diffraction of order two and above at many frequencies, with kernels per octave.

    The number of edge points follows the wavelength: frequencies are grouped in octaves
    below the highest one, each solved with a kernel built for its band. Values found in
    ``cache`` (keyed by frequency) are reused and new ones stored there, so a long
    computation can be resumed. Past ``deadline`` (a ``time.perf_counter()`` value) it
    stops with :class:`BudgetExceededError`, keeping what it solved in the cache.
    """
    import time  # noqa: PLC0415

    rec = source if receiver is None else receiver
    f = np.atleast_1d(np.asarray(frequency_hz, dtype=np.float64))
    cache = {} if cache is None else cache
    todo = sorted({float(x) for x in f if float(x) not in cache})
    if todo:
        top = max(todo)
        upper_edges = [top / 2**k for k in range(12)]
        done = len(f) - len(todo)
        for k, upper in enumerate(upper_edges):
            lower = upper_edges[k + 1] if k + 1 < len(upper_edges) else 0.0
            band = [x for x in todo if lower < x <= upper]
            if not band:
                continue
            kernel = build_kernel(plate, source, rec, upper, c=c)
            for x in band:
                if deadline is not None and time.perf_counter() > deadline:
                    raise BudgetExceededError(0.0, done, len(f))
                cache[x] = higher_order_response(kernel, x, c=c)
                done += 1
    return np.array([cache[float(x)] for x in f], dtype=np.complex128)


def frequency_response(
    plate: Plate,
    source: ArrayLike,
    receiver: ArrayLike | None,
    frequency_hz: ArrayLike,
    *,
    c: float = SPEED_OF_SOUND,
    cache: dict[float, complex] | None = None,
    deadline: float | None = None,
) -> ComplexArray:
    """Echo with diffraction of all orders over a wide band (kernels per octave)."""
    rec = source if receiver is None else receiver
    f = np.atleast_1d(np.asarray(frequency_hz, dtype=np.float64))
    first = plate_echo(plate, source, rec, f_max=float(f.max()), c=c).frequency_response(f)
    higher = higher_order_responses(plate, source, rec, f, c=c, cache=cache, deadline=deadline)
    return np.asarray(first + higher, dtype=np.complex128)
