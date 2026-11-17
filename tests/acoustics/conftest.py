# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Wave-solver reference runs shared by the acoustics tests (computed once per session)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from soundsight.acoustics.canonical import CLICK_BAND_HZ
from soundsight.acoustics.reference import fdtd
from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND

#: Band levels are evaluated at fixed frequencies, never at FFT bins: bins move with the
#: recording length and, on a steep spectrum, that alone shifts a band average by up to
#: half a decibel (EXP-0003, amendment 2).
CLICK_BAND_FREQUENCIES = np.linspace(CLICK_BAND_HZ[0], CLICK_BAND_HZ[1], 41)


def disk_run(
    radius_m: float,
    radius_cells: int,
    distance_m: float,
    peak_hz: float,
    frequencies_hz: np.ndarray | None = None,
) -> fdtd.EchoRatio:
    """Run the wave solver for a disk of a given acoustic radius and distance."""
    h = radius_m / (radius_cells + fdtd.DISK_EDGE_OFFSET_CELLS)
    return fdtd.monostatic_echo_ratio(
        "disk",
        distance_cells=round(distance_m / h + 0.5),
        radius_cells=radius_cells,
        h=h,
        peak_frequency_hz=peak_hz,
        frequencies_hz=frequencies_hz,
    )


@pytest.fixture(scope="session")
def disk_5cm() -> fdtd.EchoRatio:
    """A disk of 5 cm radius 1 m ahead, excited over the click band.

    12 cells per radius: at 6 cells the model errors came out 0.25 dB smaller than at
    12 or 18 cells (-0.56, -0.78, -0.81 dB), which would flatter every model.
    """
    return disk_run(0.05, 12, 1.0, 2500.0, CLICK_BAND_FREQUENCIES)


@pytest.fixture(scope="session")
def disk_10cm() -> fdtd.EchoRatio:
    """A disk of 10 cm radius 1 m ahead, excited over the click band."""
    return disk_run(0.10, 12, 1.0, 2500.0, CLICK_BAND_FREQUENCIES)


@pytest.fixture(scope="session")
def disk_wide() -> fdtd.EchoRatio:
    """A disk with radius 0.3 of its distance, covering ka from about 2 to 12."""
    return disk_run(0.3, 20, 1.0, 910.0)


@pytest.fixture(scope="session")
def disk_compact() -> fdtd.EchoRatio:
    """A disk far smaller than the wavelength (ka from about 0.2), 8 cells in radius."""
    peak = 0.5 * SPEED_OF_SOUND / (2.0 * 3.141592653589793 * 0.1)
    h = 0.1 / (8 + fdtd.DISK_EDGE_OFFSET_CELLS)
    return fdtd.monostatic_echo_ratio(
        "disk", distance_cells=64, radius_cells=8, h=h, peak_frequency_hz=peak
    )


@pytest.fixture(scope="session")
def disk_transition() -> fdtd.EchoRatio:
    """A disk about a wavelength in circumference, at 11 fixed ka from 1.0 to 1.5."""
    radius = 0.1
    ka = np.linspace(1.0, 1.5, 11)
    return disk_run(
        radius,
        10,
        0.77,
        SPEED_OF_SOUND / (2.0 * math.pi * radius),
        ka * SPEED_OF_SOUND / (2.0 * math.pi * radius),
    )
