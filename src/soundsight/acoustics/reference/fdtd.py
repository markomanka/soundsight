# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
r"""A small wave solver used as numerical ground truth: axisymmetric FDTD.

It solves the linear acoustic equations

.. math::

    \partial_t \mathbf{v} = -\nabla p, \qquad \partial_t p = -c^2\, \nabla\!\cdot\mathbf{v}

(unit density) in cylindrical coordinates :math:`(r, z)` with no dependence on the
angle, on a staggered grid with leapfrog time stepping. Pressure lives at cell centres
:math:`((i+\tfrac12)h, (j+\tfrac12)h)`, radial velocity on the faces :math:`r = ih` and
axial velocity on the faces :math:`z = jh`. Rigid bodies are faces whose normal
velocity is held at zero, so an infinitely thin rigid disk perpendicular to the axis is
represented exactly; curved bodies are staircased.

Scope. This is a *reference*, not a product engine: it covers scenes that are
rotationally symmetric about the line from the listener through the object (a disk or
sphere straight ahead, a wall), which is where exact and approximate formulas need a
referee. Outer walls are rigid; :func:`monostatic_echo_ratio` makes the domain large
enough that their reflections arrive after the recording ends, so they never
contaminate a result.

Because linear acoustics is scale-invariant, results depend only on sizes measured in
wavelengths. Tests therefore run at whatever scale is cheapest and still hold at
echolocation frequencies.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND, ComplexArray

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

#: Courant number c*dt/h. The scheme is stable below 1/sqrt(2); 0.6 leaves a margin.
COURANT = 0.6

#: Sub-cell correction to the radius of a thin disk. On a staggered grid the rim acts as
#: if it lay between grid points: a disk drawn ``n`` cells wide scatters like one of
#: radius ``(n + 0.35) * h``. The value is calibrated against the exact long-wavelength
#: limit (:func:`~soundsight.acoustics.reference.analytic.compact_disk_echo_ratio`) and
#: pinned by a test at two resolutions.
DISK_EDGE_OFFSET_CELLS = 0.35


@dataclass(frozen=True)
class Grid:
    """A uniform axisymmetric grid of ``n_r`` by ``n_z`` square cells of side ``h``."""

    n_r: int
    n_z: int
    h: float
    c: float = SPEED_OF_SOUND

    def __post_init__(self) -> None:
        """Validate the grid."""
        if self.n_r < 2 or self.n_z < 2:  # noqa: PLR2004
            msg = "the grid needs at least 2 cells in each direction"
            raise ValueError(msg)
        if not (self.h > 0.0 and self.c > 0.0):
            msg = "cell size and speed of sound must be positive"
            raise ValueError(msg)

    @property
    def dt(self) -> float:
        """Time step in seconds."""
        return COURANT * self.h / self.c


@dataclass(frozen=True)
class RigidFaces:
    """Faces held at zero normal velocity, as boolean masks.

    ``radial`` has shape ``(n_r + 1, n_z)`` and ``axial`` shape ``(n_r, n_z + 1)``.
    """

    radial: BoolArray
    axial: BoolArray


def no_scatterer(grid: Grid) -> RigidFaces:
    """Return masks with no rigid faces (free field inside the outer walls)."""
    return RigidFaces(
        np.zeros((grid.n_r + 1, grid.n_z), dtype=bool),
        np.zeros((grid.n_r, grid.n_z + 1), dtype=bool),
    )


def thin_disk(grid: Grid, face_index: int, radius_cells: int) -> RigidFaces:
    """Return a rigid, infinitely thin disk on the plane ``z = face_index * h``.

    Its acoustic radius is ``(radius_cells + DISK_EDGE_OFFSET_CELLS) * h``.
    ``radius_cells >= n_r`` gives a wall across the whole domain.
    """
    if not 0 < face_index < grid.n_z:
        msg = "the disk must lie strictly inside the domain"
        raise ValueError(msg)
    if radius_cells < 1:
        msg = "radius_cells must be at least 1"
        raise ValueError(msg)
    faces = no_scatterer(grid)
    faces.axial[: min(radius_cells, grid.n_r), face_index] = True
    return faces


def sphere(grid: Grid, centre_face_index: int, radius_cells: int) -> RigidFaces:
    """Return a rigid sphere centred on the axis at ``z = centre_face_index * h`` (staircased)."""
    if radius_cells < 1:
        msg = "radius_cells must be at least 1"
        raise ValueError(msg)
    if not radius_cells < centre_face_index < grid.n_z - radius_cells:
        msg = "the sphere must lie strictly inside the domain"
        raise ValueError(msg)
    r = (np.arange(grid.n_r) + 0.5)[:, None]
    z = (np.arange(grid.n_z) + 0.5)[None, :] - centre_face_index
    solid = r**2 + z**2 < radius_cells**2
    faces = no_scatterer(grid)
    # A face is rigid when it touches a solid cell on either side.
    faces.radial[:-1, :] |= solid
    faces.radial[1:, :] |= solid
    faces.axial[:, :-1] |= solid
    faces.axial[:, 1:] |= solid
    return faces


def ricker(peak_frequency_hz: float, dt: float) -> FloatArray:
    """Return a Ricker pulse sampled at ``dt``, starting and ending below 1e-9 of its peak.

    Its spectrum peaks at ``peak_frequency_hz`` and is usable from about a third of
    that to about twice that.
    """
    if not peak_frequency_hz > 0.0:
        msg = "peak_frequency_hz must be positive"
        raise ValueError(msg)
    t0 = 1.5 / peak_frequency_hz
    t = np.arange(math.ceil(2.0 * t0 / dt) + 1) * dt - t0
    x = (math.pi * peak_frequency_hz * t) ** 2
    return np.asarray((1.0 - 2.0 * x) * np.exp(-x), dtype=np.float64)


def simulate(
    grid: Grid,
    faces: RigidFaces,
    *,
    source_cell_z: int,
    pulse: FloatArray,
    probe_cells_z: tuple[int, ...],
    n_steps: int,
    monitor: Callable[[int, FloatArray, FloatArray, FloatArray], None] | None = None,
) -> FloatArray:
    """Run the solver and return the pressure recorded on the axis.

    Parameters
    ----------
    grid
        The grid.
    faces
        Rigid faces of the scatterer. The outer walls and the axis are always rigid.
    source_cell_z
        Axial index of the on-axis cell where ``pulse`` is injected.
    pulse
        Source signal, one value per time step (zero after its end).
    probe_cells_z
        Axial indices of on-axis cells whose pressure is recorded.
    n_steps
        Number of time steps.
    monitor
        Optional callback ``monitor(step, p, v_r, v_z)`` called after every step.

    Returns
    -------
    numpy.ndarray
        Pressure, shape ``(n_steps, len(probe_cells_z))``.
    """
    for cell in (source_cell_z, *probe_cells_z):
        if not 0 <= cell < grid.n_z:
            msg = f"cell index {cell} is outside the grid"
            raise ValueError(msg)
    p = np.zeros((grid.n_r, grid.n_z))
    v_r = np.zeros((grid.n_r + 1, grid.n_z))
    v_z = np.zeros((grid.n_r, grid.n_z + 1))
    keep_r = ~faces.radial[1:-1, :]
    keep_z = ~faces.axial[:, 1:-1]
    r_face = np.arange(grid.n_r + 1, dtype=np.float64)[:, None]
    inv_r_centre = 1.0 / (np.arange(grid.n_r, dtype=np.float64) + 0.5)[:, None]
    a = grid.dt / grid.h
    b = grid.dt * grid.c**2 / grid.h
    probes = list(probe_cells_z)
    record = np.zeros((n_steps, len(probes)))
    for step in range(n_steps):
        v_r[1:-1, :] -= a * (p[1:, :] - p[:-1, :])
        v_r[1:-1, :] *= keep_r
        v_z[:, 1:-1] -= a * (p[:, 1:] - p[:, :-1])
        v_z[:, 1:-1] *= keep_z
        flux_r = r_face * v_r
        p -= b * ((flux_r[1:, :] - flux_r[:-1, :]) * inv_r_centre + v_z[:, 1:] - v_z[:, :-1])
        if step < pulse.size:
            p[0, source_cell_z] += pulse[step]
        record[step] = p[0, probes]
        if monitor is not None:
            monitor(step, p, v_r, v_z)
    return record


def acoustic_energy(
    grid: Grid, p: FloatArray, p_previous: FloatArray, v_r: FloatArray, v_z: FloatArray
) -> float:
    """Discrete acoustic energy (up to a constant factor), exactly conserved by the scheme.

    In a leapfrog scheme pressure and velocity are half a step apart. The quantity the
    scheme conserves to rounding error, once the source is silent, pairs the velocity
    with the product of the pressures just before and just after it.
    """
    r_centre = (np.arange(grid.n_r) + 0.5)[:, None]
    r_face = np.arange(grid.n_r + 1, dtype=np.float64)[:, None]
    potential = float(np.sum(r_centre * p * p_previous)) / grid.c**2
    kinetic = float(np.sum(r_face * v_r**2)) + float(np.sum(r_centre * v_z**2))
    return 0.5 * (potential + kinetic)


@dataclass(frozen=True)
class EchoRatio:
    """An echo ratio computed by the wave solver, over the band the pulse excites well."""

    frequency_hz: FloatArray
    ratio: ComplexArray
    distance: float
    radius: float
    h: float


def monostatic_echo_ratio(
    shape: str,
    *,
    distance_cells: int,
    radius_cells: int,
    h: float,
    peak_frequency_hz: float,
    c: float = SPEED_OF_SOUND,
    tail_cells: int | None = None,
    band_db: float = 20.0,
) -> EchoRatio:
    """Compute the monostatic echo ratio of an on-axis rigid object with the wave solver.

    Two simulations are run with the same source: one in free field, recording the
    pulse at twice the object's distance (what a perfect mirror would send back), and
    one with the object, recording at the source. The echo ratio is the spectrum of the
    scattered signal divided by that of the mirror signal. Both signals travelled the
    same distance through the same grid, so numerical dispersion cancels to first order.

    Parameters
    ----------
    shape
        ``"disk"`` (thin, facing the listener), ``"sphere"`` or ``"wall"``.
    distance_cells
        Distance from the listener to the nearest point of the object, in cells; it is
        ``(distance_cells - 0.5) * h`` because the listener sits at a cell centre.
    radius_cells
        Radius of the disk or sphere in cells (ignored for a wall). The returned
        ``radius`` is the acoustic radius in metres: for a disk it includes
        :data:`DISK_EDGE_OFFSET_CELLS`; a sphere is staircased, so its radius is only
        accurate to about a cell.
    h
        Cell size in metres.
    peak_frequency_hz
        Peak of the source spectrum; results cover roughly a third to twice this.
    c
        Speed of sound.
    tail_cells
        Extra path length recorded after the last first-order arrival, to capture waves
        that cross the object several times. Defaults to four radii.
    band_db
        Frequencies whose mirror-signal level is within this many dB of its peak are kept.
    """
    if shape not in {"disk", "sphere", "wall"}:
        msg = f"unknown shape: {shape!r}"
        raise ValueError(msg)
    if distance_cells < 2:  # noqa: PLR2004
        msg = "distance_cells must be at least 2"
        raise ValueError(msg)
    if shape == "wall":
        radius_cells = 0
    elif radius_cells < 1:
        msg = "radius_cells must be at least 1"
        raise ValueError(msg)
    dt = COURANT * h / c
    pulse = ricker(peak_frequency_hz, dt)
    tail = 4 * radius_cells if tail_cells is None else tail_cells
    depth = 2 * radius_cells if shape == "sphere" else 0
    # Longest path of interest, in cells: out to the far rim (or round the sphere) and back.
    reach = 2.0 * math.hypot(distance_cells + depth, radius_cells) + tail
    n_steps = pulse.size + math.ceil(reach / COURANT)
    # Outer walls far enough that their reflections arrive after the last step.
    margin = math.ceil(0.5 * n_steps * COURANT) + 2
    source = margin
    face = source + distance_cells  # nearest point of the object: the plane z = face * h
    mirror = source + 2 * distance_cells - 1  # cell centre at twice the distance
    grid = Grid(n_r=margin, n_z=mirror + margin - distance_cells + 2 + depth, h=h, c=c)

    if shape == "sphere":
        faces = sphere(grid, face + radius_cells, radius_cells)
    else:
        faces = thin_disk(grid, face, grid.n_r if shape == "wall" else radius_cells)
    free = simulate(
        grid,
        no_scatterer(grid),
        source_cell_z=source,
        pulse=pulse,
        probe_cells_z=(source, mirror),
        n_steps=n_steps,
    )
    with_object = simulate(
        grid, faces, source_cell_z=source, pulse=pulse, probe_cells_z=(source,), n_steps=n_steps
    )

    reference = np.fft.rfft(free[:, 1])
    scattered = np.fft.rfft(with_object[:, 0] - free[:, 0])
    freqs = np.fft.rfftfreq(n_steps, dt)
    level = np.abs(reference)
    keep = (level >= level.max() * 10.0 ** (-band_db / 20.0)) & (freqs > 0.0)
    offset = DISK_EDGE_OFFSET_CELLS if shape == "disk" else 0.0
    return EchoRatio(
        frequency_hz=freqs[keep],
        ratio=np.asarray(scattered[keep] / reference[keep], dtype=np.complex128),
        distance=(distance_cells - 0.5) * h,
        radius=(radius_cells + offset) * h if shape != "wall" else math.inf,
        h=h,
    )
