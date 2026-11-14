# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for soundsight.click.synth: the synthesizer is the ground truth for everything."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.signal import hilbert

from soundsight.click.synth import (
    BOUNDARY_LEVEL,
    ClickParameters,
    click_train,
    envelope,
    synth_click,
)


@pytest.mark.parametrize(("duration_ms", "onset_ms"), [(3.0, 0.3), (1.0, 0.2), (6.0, 1.0)])
def test_envelope_extent_matches_duration(duration_ms: float, onset_ms: float) -> None:
    params = ClickParameters(duration_ms=duration_ms, onset_ms=onset_ms)
    fs = 1_000_000  # fine grid: 1 microsecond
    t = np.arange(round(params.length_s * fs)) / fs
    above = envelope(t, params) >= BOUNDARY_LEVEL
    extent_ms = 1000.0 * above.sum() / fs
    assert extent_ms == pytest.approx(duration_ms, abs=0.002)


def test_envelope_shape() -> None:
    params = ClickParameters(onset_ms=0.5)
    t = np.array([-1e-3, 0.0, 0.25e-3, 0.5e-3, 1.0])
    e = envelope(t, params)
    assert e[0] == 0.0
    assert e[1] == 0.0
    assert e[2] == pytest.approx(0.5)
    assert e[3] == pytest.approx(1.0)
    assert e[4] < 1e-12


def test_click_peak_amplitude_and_length() -> None:
    params = ClickParameters(amplitude=0.25)
    click = synth_click(96000, params)
    assert np.max(np.abs(click)) <= 0.25
    # The envelope (not the carrier sample nearest its maximum) reaches the amplitude.
    assert np.max(np.abs(hilbert(click))) == pytest.approx(0.25, rel=0.02)
    assert click.size == pytest.approx(params.length_s * 96000, abs=1)


def test_click_spectral_peak_is_carrier() -> None:
    click = synth_click(48000, ClickParameters(peak_frequency_hz=3500.0))
    spectrum = np.abs(np.fft.rfft(click, n=1 << 16))
    freqs = np.fft.rfftfreq(1 << 16, 1 / 48000)
    assert freqs[np.argmax(spectrum)] == pytest.approx(3500.0, rel=0.02)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"peak_frequency_hz": 0.0},
        {"onset_ms": 0.0},
        {"duration_ms": 0.1, "onset_ms": 1.0},
        {"amplitude": 0.0},
        {"amplitude": 1.5},
    ],
)
def test_invalid_parameters(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="must"):
        ClickParameters(**kwargs)


def test_synth_rejects_bad_rate_and_aliasing() -> None:
    with pytest.raises(ValueError, match="positive"):
        synth_click(0)
    with pytest.raises(ValueError, match="Nyquist"):
        synth_click(5000, ClickParameters(peak_frequency_hz=3000.0))


def test_click_train_peak_times_and_reproducibility() -> None:
    sig1, peaks = click_train(48000, 4, 0.5, start_s=0.2, noise_dbfs=-60, seed=7)
    sig2, _ = click_train(48000, 4, 0.5, start_s=0.2, noise_dbfs=-60, seed=7)
    np.testing.assert_array_equal(sig1, sig2)
    np.testing.assert_allclose(peaks, 0.2 + 0.0003 + 0.5 * np.arange(4), atol=1 / 48000)


def test_click_train_noise_level() -> None:
    sig, _ = click_train(48000, 0, 1.0, start_s=1.0, noise_dbfs=-40, seed=0)
    rms_db = 20 * np.log10(np.sqrt(np.mean(sig**2)))
    assert rms_db == pytest.approx(-40, abs=0.2)


def test_click_train_level_jitter_changes_levels() -> None:
    sig, peaks = click_train(48000, 5, 0.2, level_jitter_db=3.0, seed=3)
    levels = [np.max(np.abs(sig[round(p * 48000) - 50 : round(p * 48000) + 50])) for p in peaks]
    assert np.std(levels) > 0.0


@pytest.mark.parametrize(("n", "interval"), [(-1, 1.0), (1, 0.0)])
def test_click_train_rejects_bad_arguments(n: int, interval: float) -> None:
    with pytest.raises(ValueError, match="must be"):
        click_train(48000, n, interval)
