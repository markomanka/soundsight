# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Candidate R3 of EXP-0006: exercise trials from a per-disc echo cache.

R2 (:mod:`soundsight.exercise.render_all_orders`) solves the all-orders equation for
every trial, at every frequency where the click has energy; with a sharp click that
exceeds the cost budget (EXP-0005). But diffraction of order two and above depends only
on the disc and its distance, not on the click. R3 computes it once per disc, on a fixed
grid, and reuses it for every click and trial.

Every higher-order path is longer than the mirror path, so these arrivals come after the
mirror echo at ``t0 = 2 d / c``. The cache stores the response relative to ``t0``
(rounded down to a sample) over a window of :data:`WINDOW_S`, which fixes the frequency
spacing at ``1 / WINDOW_S``; frequencies run from zero up to 0.45 times the sample rate.
The zero-frequency term matters: there the higher orders largely cancel first order (a
small disc barely echoes at long wavelengths), and leaving it out spreads an offset over
the whole window (design check, EXP-0006). A trial's
impulse response is R1's first-order response plus this window placed at ``t0``.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from soundsight.acoustics import engine as _engine
from soundsight.acoustics.candidates import all_orders
from soundsight.acoustics.canonical import band_level_db
from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND, plane_echo
from soundsight.audio import FloatArray, Recording, from_array
from soundsight.click.synth import ClickParameters, synth_click
from soundsight.exercise.render import BAND_FREQUENCIES_HZ, PEAK_NORMALIZATION, TrialReport
from soundsight.exercise.render_all_orders import (
    ALL_ORDERS_SIDES,
    PASSBAND,
    dtft,
    first_order_impulse_response,
)

#: Length of the higher-order response kept after the mirror echo, in seconds: about 14
#: rim-to-rim crossings of the largest protocol disc (25.4 cm).
WINDOW_S = 0.010


@dataclass(frozen=True)
class DiscEchoCache:
    """Diffraction of order two and above for one disc, on a fixed frequency grid."""

    diameter_m: float
    distance_m: float
    sample_rate: int
    frequency_hz: FloatArray
    higher: np.ndarray
    build_seconds: float

    @property
    def onset_samples(self) -> int:
        """The mirror echo's arrival, in whole samples, where the window starts."""
        return math.floor(2.0 * self.distance_m / SPEED_OF_SOUND * self.sample_rate)

    @property
    def window_samples(self) -> int:
        """Length of the window in samples."""
        return round(WINDOW_S * self.sample_rate)


def cache_grid(sample_rate: int) -> FloatArray:
    """Return the cache's frequencies: multiples of ``1 / WINDOW_S`` from zero to the passband."""
    n = round(WINDOW_S * sample_rate)
    f = np.fft.rfftfreq(n, 1.0 / sample_rate)
    return np.asarray(f[f <= PASSBAND * sample_rate], dtype=np.float64)


def build_cache(
    diameter_m: float,
    distance_m: float,
    sample_rate: int = 48_000,
    *,
    c: float = SPEED_OF_SOUND,
    store: dict[float, complex] | None = None,
    deadline: float | None = None,
) -> DiscEchoCache:
    """Solve the higher orders of one disc on the cache grid (resumable through ``store``)."""
    started = time.perf_counter()
    plate = _engine.Plate.regular(diameter_m / 2.0, ALL_ORDERS_SIDES, centre=(0.0, 0.0, distance_m))
    f = cache_grid(sample_rate)
    higher = all_orders.higher_order_responses(
        plate, (0.0, 0.0, 0.0), None, f, c=c, cache=store, deadline=deadline
    )
    return DiscEchoCache(
        diameter_m, distance_m, sample_rate, f, higher, time.perf_counter() - started
    )


def higher_order_window(cache: DiscEchoCache) -> FloatArray:
    """Return the higher-order impulse response over the window from the mirror echo on."""
    n = cache.window_samples
    shift = cache.onset_samples / cache.sample_rate
    spectrum = np.zeros(n // 2 + 1, dtype=np.complex128)
    bins = np.rint(cache.frequency_hz * n / cache.sample_rate).astype(int)
    spectrum[bins] = cache.higher * np.exp(2j * np.pi * cache.frequency_hz * shift)
    return np.asarray(np.fft.irfft(spectrum, n=n), dtype=np.float64)


def cached_impulse_response(cache: DiscEchoCache, c: float = SPEED_OF_SOUND) -> FloatArray:
    """R3's impulse response for a unit source: R1's plus the cached higher orders."""
    first = first_order_impulse_response(cache.diameter_m, cache.distance_m, cache.sample_rate, c)
    window = higher_order_window(cache)
    start = cache.onset_samples
    ir = np.zeros(max(first.size, start + window.size))
    ir[: first.size] += first
    ir[start : start + window.size] += window
    return ir


def render_trial_from_cache(
    cache: DiscEchoCache,
    *,
    click_reference_distance_m: float,
    click: FloatArray | None = None,
    click_params: ClickParameters | None = None,
    c: float = SPEED_OF_SOUND,
) -> tuple[Recording, TrialReport]:
    """Render one trial from a disc's cache (same conventions as R1 and R2)."""
    if not click_reference_distance_m > 0.0:
        msg = f"click_reference_distance_m must be positive, got {click_reference_distance_m}"
        raise ValueError(msg)
    fs = cache.sample_rate
    if click is None:
        click = synth_click(fs, click_params)
    elif click_params is not None:
        msg = "pass either click or click_params, not both"
        raise ValueError(msg)
    click = np.asarray(click, dtype=np.float64)
    started = time.perf_counter()
    ir = cached_impulse_response(cache, c)
    n = click.size + ir.size - 1
    echo = np.fft.irfft(np.fft.rfft(click, n) * np.fft.rfft(ir, n), n) * click_reference_distance_m
    mix = echo.copy()
    mix[: click.size] += click
    gain = PEAK_NORMALIZATION / float(np.max(np.abs(mix)))
    response = dtft(ir, fs, BAND_FREQUENCIES_HZ)
    delay = int(np.argmax(np.abs(ir))) / fs
    report = TrialReport(
        disc_diameter_m=cache.diameter_m,
        disc_distance_m=cache.distance_m,
        echo_delay_s=delay,
        echo_distance_m=c * delay / 2.0,
        echo_band_level_db=band_level_db(response) + 20.0 * math.log10(click_reference_distance_m),
        echo_ratio_db=band_level_db(
            response / plane_echo(BAND_FREQUENCIES_HZ, cache.distance_m, c)
        ),
        click_reference_distance_m=click_reference_distance_m,
        n_arrivals=0,
        n_specular=1,
        normalization_gain=gain,
        render_seconds=time.perf_counter() - started,
    )
    return from_array(mix * gain, fs), report
