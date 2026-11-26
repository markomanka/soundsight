# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Candidate R2 of EXP-0005: exercise trials with diffraction of all orders.

R1 (:mod:`soundsight.exercise.render`, contributed by Kimi) renders first-order
diffraction in the time domain. R2 adds diffraction of order two and above from the
engine's increment 2 (:mod:`soundsight.acoustics.candidates.all_orders`), solved only
at the FFT frequencies of the trial where the click's power spectrum is within 60 dB of
its peak, up to 0.45 times the sample rate (where rendered responses are accurate), and
added to R1's impulse response by inverse FFT. Elsewhere the click carries no energy
worth an error, which is what makes the trial cheaper than a full-band response.
"""

from __future__ import annotations

import math
import time

import numpy as np

from soundsight.acoustics import engine as _engine
from soundsight.acoustics.candidates import all_orders
from soundsight.acoustics.canonical import band_level_db
from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND, plane_echo
from soundsight.audio import FloatArray, Recording, from_array
from soundsight.click.synth import ClickParameters, synth_click
from soundsight.exercise.render import (
    BAND_FREQUENCIES_HZ,
    DEFAULT_DISC_SIDES,
    IR_MARGIN_S,
    PEAK_NORMALIZATION,
    TrialReport,
    disc_plate,
)

#: Bins whose click power is this many dB below the click's peak are not solved.
CLICK_POWER_FLOOR_DB = 60.0
#: Highest solved frequency, as a fraction of the sample rate.
PASSBAND = 0.45
#: Sides of the polygon on which the higher orders are solved (C2's configuration).
ALL_ORDERS_SIDES = 48


def dtft(signal: FloatArray, sample_rate: int, frequency_hz: FloatArray) -> np.ndarray:
    """Discrete-time Fourier transform of ``signal`` at arbitrary frequencies."""
    n = np.arange(signal.size)
    kernel = np.exp(-2j * np.pi * np.outer(frequency_hz, n) / sample_rate)
    return np.asarray(kernel @ signal, dtype=np.complex128)


def first_order_impulse_response(
    diameter_m: float, distance_m: float, sample_rate: int, c: float = SPEED_OF_SOUND
) -> FloatArray:
    """R1's impulse response for a unit source, computed exactly as R1 computes it."""
    plate = disc_plate(diameter_m, distance_m, DEFAULT_DISC_SIDES)
    arrivals = _engine.plate_echo(plate, (0.0, 0.0, 0.0), f_max=sample_rate / 2.0, c=c)
    last = float(arrivals.delays.max(initial=0.0))
    n_ir = max(2 * 32 + 2, math.ceil((last + IR_MARGIN_S) * sample_rate))
    return _engine.render(arrivals, sample_rate, n_ir)


def solved_bins(click: FloatArray, n: int, sample_rate: int) -> np.ndarray:
    """Return the indices of the FFT bins (length ``n``) that R2 solves for this click."""
    power = np.abs(np.fft.rfft(click, n)) ** 2
    f = np.fft.rfftfreq(n, 1.0 / sample_rate)
    keep = (power >= power.max() * 10.0 ** (-CLICK_POWER_FLOOR_DB / 10.0)) & (f > 0.0)
    return np.flatnonzero(keep & (f <= PASSBAND * sample_rate))


def all_orders_impulse_response(
    diameter_m: float,
    distance_m: float,
    click: FloatArray,
    sample_rate: int,
    *,
    c: float = SPEED_OF_SOUND,
    cache: dict[float, complex] | None = None,
    deadline: float | None = None,
) -> FloatArray:
    """R2's impulse response for a unit source, the length of the trial."""
    first = first_order_impulse_response(diameter_m, distance_m, sample_rate, c)
    n = click.size + first.size - 1
    bins = solved_bins(click, n, sample_rate)
    f = np.fft.rfftfreq(n, 1.0 / sample_rate)
    plate = _engine.Plate.regular(diameter_m / 2.0, ALL_ORDERS_SIDES, centre=(0.0, 0.0, distance_m))
    spectrum = np.zeros(f.size, dtype=np.complex128)
    spectrum[bins] = all_orders.higher_order_responses(
        plate, (0.0, 0.0, 0.0), None, f[bins], c=c, cache=cache, deadline=deadline
    )
    ir = np.fft.irfft(spectrum, n=n)
    ir[: first.size] += first
    return np.asarray(ir, dtype=np.float64)


def render_disc_trial_all_orders(
    diameter_m: float,
    distance_m: float,
    *,
    click_reference_distance_m: float,
    sample_rate: int = 48_000,
    click: FloatArray | None = None,
    click_params: ClickParameters | None = None,
    c: float = SPEED_OF_SOUND,
    deadline: float | None = None,
) -> tuple[Recording, TrialReport]:
    """Render one trial with diffraction of all orders (same conventions as R1)."""
    if not click_reference_distance_m > 0.0:
        msg = f"click_reference_distance_m must be positive, got {click_reference_distance_m}"
        raise ValueError(msg)
    if click is None:
        click = synth_click(sample_rate, click_params)
    elif click_params is not None:
        msg = "pass either click or click_params, not both"
        raise ValueError(msg)
    click = np.asarray(click, dtype=np.float64)
    started = time.perf_counter()
    ir = all_orders_impulse_response(
        diameter_m, distance_m, click, sample_rate, c=c, deadline=deadline
    )
    n = ir.size
    echo = np.fft.irfft(np.fft.rfft(click, n) * np.fft.rfft(ir) * click_reference_distance_m, n)
    mix = echo.copy()
    mix[: click.size] += click
    gain = PEAK_NORMALIZATION / float(np.max(np.abs(mix)))
    response = dtft(ir, sample_rate, BAND_FREQUENCIES_HZ)
    first_peak = int(np.argmax(np.abs(ir)))
    delay = first_peak / sample_rate
    report = TrialReport(
        disc_diameter_m=diameter_m,
        disc_distance_m=distance_m,
        echo_delay_s=delay,
        echo_distance_m=c * delay / 2.0,
        echo_band_level_db=band_level_db(response) + 20.0 * math.log10(click_reference_distance_m),
        echo_ratio_db=band_level_db(response / plane_echo(BAND_FREQUENCIES_HZ, distance_m, c)),
        click_reference_distance_m=click_reference_distance_m,
        n_arrivals=0,
        n_specular=1,
        normalization_gain=gain,
        render_seconds=time.perf_counter() - started,
    )
    return from_array(mix * gain, sample_rate), report
