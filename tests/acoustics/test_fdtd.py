# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""The wave solver must earn its role as referee: every test here checks it against
exact theory or against a property the equations guarantee."""

from __future__ import annotations

import numpy as np
import pytest

from soundsight.acoustics.reference import analytic as an
from soundsight.acoustics.reference import fdtd

C = an.SPEED_OF_SOUND


def _free_field_phase_and_amplitude_error(h: float) -> tuple[float, float]:
    n = round(2.2 / h)
    grid = fdtd.Grid(n_r=n, n_z=2 * n, h=h)
    probes = (n + round(0.4 / h), n + round(1.2 / h))
    rec = fdtd.simulate(
        grid,
        fdtd.no_scatterer(grid),
        source_cell_z=n,
        pulse=fdtd.ricker(1500.0, grid.dt),
        probe_cells_z=probes,
        n_steps=int(2.3 / (0.6 * h)),
    )
    spectrum = np.fft.rfft(rec, axis=0)
    f = np.fft.rfftfreq(rec.shape[0], grid.dt)
    band = (f > 800) & (f < 2500)
    q = (spectrum[band, 1] / spectrum[band, 0]) / (
        an.free_field(f[band], 1.2) / an.free_field(f[band], 0.4)
    )
    return float(np.abs(np.angle(q)).max()), float(np.abs(np.abs(q) - 1).max())


def test_free_field_obeys_inverse_distance_law() -> None:
    _, amplitude_error = _free_field_phase_and_amplitude_error(0.02)
    assert amplitude_error < 1e-3


def test_phase_error_converges_at_second_order() -> None:
    coarse, _ = _free_field_phase_and_amplitude_error(0.02)
    fine, _ = _free_field_phase_and_amplitude_error(0.01)
    assert 3.5 < coarse / fine < 4.6  # halving the cell size divides the error by 4


def test_wall_echo_ratio_is_exactly_one() -> None:
    wall = fdtd.monostatic_echo_ratio(
        "wall", distance_cells=40, radius_cells=0, h=0.01, peak_frequency_hz=1500.0
    )
    assert np.abs(wall.ratio - 1.0).max() < 1e-6
    assert wall.radius == np.inf
    assert wall.distance == pytest.approx(0.395)


def test_energy_is_conserved_in_a_rigid_box() -> None:
    """With rigid walls and no damping the discrete energy must stay constant to rounding."""
    grid = fdtd.Grid(n_r=60, n_z=120, h=0.01)
    pulse = fdtd.ricker(2000.0, grid.dt)
    energies: list[float] = []
    previous = np.zeros((grid.n_r, grid.n_z))

    def monitor(step: int, p: np.ndarray, v_r: np.ndarray, v_z: np.ndarray) -> None:
        if step > pulse.size:
            energies.append(fdtd.acoustic_energy(grid, p, previous, v_r, v_z))
        previous[:] = p

    fdtd.simulate(
        grid,
        fdtd.thin_disk(grid, 80, 25),
        source_cell_z=40,
        pulse=pulse,
        probe_cells_z=(40,),
        n_steps=1500,
        monitor=monitor,
    )
    e = np.array(energies)
    assert e.size > 1000
    assert e.min() > 0
    assert np.ptp(e) / e.mean() < 1e-9


def test_sphere_error_shrinks_with_refinement() -> None:
    errors = []
    for radius_cells in (8, 16):
        run = fdtd.monostatic_echo_ratio(
            "sphere",
            distance_cells=int(1.5 * radius_cells),
            radius_cells=radius_cells,
            h=0.3 / radius_cells,
            peak_frequency_hz=330.0,
        )
        exact = an.sphere_echo_ratio(run.frequency_hz, run.radius, run.distance + run.radius)
        low = 2 * np.pi * run.frequency_hz * run.radius / C <= 3.0
        errors.append(float((np.abs(run.ratio[low] - exact[low]) / np.abs(exact[low])).mean()))
    assert errors[1] < 0.10
    assert errors[1] < 0.5 * errors[0]


def test_small_disk_matches_exact_long_wavelength_limit(disk_compact: fdtd.EchoRatio) -> None:
    """Pins DISK_EDGE_OFFSET_CELLS: without it the echo is 13% too strong at 8 cells."""
    run = disk_compact
    ka = 2 * np.pi * run.frequency_hz * run.radius / C
    lowest = int(np.argmin(ka))
    assert ka[lowest] < 0.25
    q = (
        run.ratio[lowest]
        / an.compact_disk_echo_ratio([run.frequency_hz[lowest]], run.radius, run.distance)[0]
    )
    assert abs(q) == pytest.approx(1.0, abs=0.03)
    assert np.angle(q) == pytest.approx(0.0, abs=0.03)


def test_disk_echo_is_resolution_independent(
    disk_5cm: fdtd.EchoRatio, disk_10cm: fdtd.EchoRatio
) -> None:
    """Fine-grid values recorded on 2026-11-15 (8 and 16 cells per radius)."""
    for run, fine_level in ((disk_5cm, -15.7), (disk_10cm, -5.0)):
        band = (run.frequency_hz >= 2000) & (run.frequency_hz <= 4000)
        level = 10 * np.log10(np.mean(np.abs(run.ratio[band]) ** 2))
        assert level == pytest.approx(fine_level, abs=0.3)


@pytest.mark.slow
def test_edge_offset_holds_at_finer_resolution() -> None:
    peak = 0.5 * C / (2 * np.pi * 0.1)
    h = 0.1 / (16 + fdtd.DISK_EDGE_OFFSET_CELLS)
    run = fdtd.monostatic_echo_ratio(
        "disk", distance_cells=128, radius_cells=16, h=h, peak_frequency_hz=peak
    )
    lowest = int(np.argmin(run.frequency_hz))
    q = (
        run.ratio[lowest]
        / an.compact_disk_echo_ratio([run.frequency_hz[lowest]], run.radius, run.distance)[0]
    )
    assert abs(q) == pytest.approx(1.0, abs=0.02)


@pytest.mark.slow
def test_sphere_error_keeps_shrinking_on_a_fine_grid() -> None:
    run = fdtd.monostatic_echo_ratio(
        "sphere", distance_cells=48, radius_cells=32, h=0.3 / 32, peak_frequency_hz=330.0
    )
    exact = an.sphere_echo_ratio(run.frequency_hz, run.radius, run.distance + run.radius)
    low = 2 * np.pi * run.frequency_hz * run.radius / C <= 3.0
    assert float((np.abs(run.ratio[low] - exact[low]) / np.abs(exact[low])).mean()) < 0.05


def test_ricker_pulse_starts_and_ends_silent() -> None:
    pulse = fdtd.ricker(1000.0, 1e-5)
    assert abs(pulse[0]) < 1e-8
    assert abs(pulse[-1]) < 1e-8
    assert pulse.max() == pytest.approx(1.0, abs=1e-3)
    spectrum = np.abs(np.fft.rfft(pulse, n=1 << 16))
    peak = np.fft.rfftfreq(1 << 16, 1e-5)[np.argmax(spectrum)]
    assert peak == pytest.approx(1000.0, rel=0.01)


def test_time_step_respects_stability_limit() -> None:
    grid = fdtd.Grid(n_r=10, n_z=10, h=0.01)
    assert grid.c * grid.dt / grid.h == pytest.approx(fdtd.COURANT)
    assert 1 / np.sqrt(2) > fdtd.COURANT


def test_sphere_mask_makes_touching_faces_rigid() -> None:
    grid = fdtd.Grid(n_r=20, n_z=40, h=0.01)
    faces = fdtd.sphere(grid, 20, 5)
    assert faces.axial[0, 15]  # nearest point of the sphere, on the axis
    assert faces.axial[0, 25]
    assert not faces.axial[0, 14]
    assert faces.radial[5, 20]
    assert not faces.radial[7, 20]


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: fdtd.Grid(1, 10, 0.01), "at least 2 cells"),
        (lambda: fdtd.Grid(10, 10, 0.0), "must be positive"),
        (lambda: fdtd.thin_disk(fdtd.Grid(10, 10, 0.01), 0, 3), "strictly inside"),
        (lambda: fdtd.thin_disk(fdtd.Grid(10, 10, 0.01), 5, 0), "at least 1"),
        (lambda: fdtd.sphere(fdtd.Grid(10, 10, 0.01), 5, 0), "at least 1"),
        (lambda: fdtd.sphere(fdtd.Grid(10, 10, 0.01), 2, 3), "strictly inside"),
        (lambda: fdtd.ricker(0.0, 1e-5), "must be positive"),
        (
            lambda: fdtd.simulate(
                fdtd.Grid(4, 4, 0.01),
                fdtd.no_scatterer(fdtd.Grid(4, 4, 0.01)),
                source_cell_z=9,
                pulse=np.ones(1),
                probe_cells_z=(0,),
                n_steps=1,
            ),
            "outside the grid",
        ),
        (
            lambda: fdtd.monostatic_echo_ratio(
                "cube", distance_cells=10, radius_cells=2, h=0.01, peak_frequency_hz=1e3
            ),
            "unknown shape",
        ),
        (
            lambda: fdtd.monostatic_echo_ratio(
                "disk", distance_cells=1, radius_cells=2, h=0.01, peak_frequency_hz=1e3
            ),
            "at least 2",
        ),
        (
            lambda: fdtd.monostatic_echo_ratio(
                "disk", distance_cells=10, radius_cells=0, h=0.01, peak_frequency_hz=1e3
            ),
            "at least 1",
        ),
    ],
)
def test_invalid_inputs_are_rejected(call, message: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match=message):
        call()
