# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Detection and measurement must recover the synthesizer's ground truth."""

from __future__ import annotations

import numpy as np
import pytest

from soundsight.click.detect import DetectionSettings, detect_clicks
from soundsight.click.features import measure_click
from soundsight.click.synth import ClickParameters, click_train

RATES = [44100, 48000, 96000, 192000]


@pytest.mark.parametrize("fs", RATES)
@pytest.mark.parametrize(("peak_hz", "duration_ms"), [(3000.0, 3.0), (2200.0, 2.0), (4500.0, 4.5)])
def test_recovers_ground_truth(fs: int, peak_hz: float, duration_ms: float) -> None:
    params = ClickParameters(peak_frequency_hz=peak_hz, duration_ms=duration_ms, amplitude=0.5)
    x, peaks = click_train(fs, 6, 0.4, params, noise_dbfs=-70, seed=11)
    det = detect_clicks(x, fs)
    assert len(det.events) == 6
    for event, true_peak in zip(det.events, peaks, strict=True):
        assert event.peak_index / fs == pytest.approx(true_peak, abs=0.3e-3)
        assert not event.truncated
        f = measure_click(x, fs, event, det.envelope, det.noise_floor)
        assert f.duration_ms == pytest.approx(duration_ms, rel=0.08)
        assert f.peak_frequency_hz == pytest.approx(peak_hz, rel=0.02)
        assert f.centroid_hz == pytest.approx(peak_hz, rel=0.15)
        assert f.peak_dbfs == pytest.approx(20 * np.log10(0.5), abs=0.5)
        assert f.bandwidth_hz > 0
        assert not f.clipped


def test_snr_reflects_noise_floor() -> None:
    fs = 48000
    x, _ = click_train(fs, 5, 0.3, ClickParameters(amplitude=0.5), noise_dbfs=-50, seed=2)
    det = detect_clicks(x, fs)
    f = measure_click(x, fs, det.events[0], det.envelope, det.noise_floor)
    # Median of the Rayleigh-distributed noise envelope is sigma * sqrt(2 ln 2) = 1.18 sigma.
    expected = 20 * np.log10(0.5) - (-50 + 20 * np.log10(np.sqrt(2 * np.log(2))))
    assert f.snr_db == pytest.approx(expected, abs=1.0)


def test_pure_noise_has_no_clicks() -> None:
    rng = np.random.default_rng(5)
    x = rng.normal(0, 0.01, 192000 * 3)
    assert detect_clicks(x, 192000).events == ()


def test_digital_silence_has_no_clicks() -> None:
    det = detect_clicks(np.zeros(48000), 48000)
    assert det.events == ()
    assert det.noise_floor > 0


def test_weak_outlier_is_ignored() -> None:
    fs = 48000
    loud, _ = click_train(fs, 3, 0.3, ClickParameters(amplitude=0.5), noise_dbfs=-100, seed=1)
    weak, _ = click_train(fs, 1, 0.3, ClickParameters(amplitude=0.005), start_s=1.2, seed=1)
    x = np.zeros(max(loud.size, weak.size))
    x[: loud.size] += loud
    x[: weak.size] += weak
    assert len(detect_clicks(x, fs).events) == 3


def test_min_interval_merges_close_peaks() -> None:
    fs = 48000
    x, _ = click_train(fs, 2, 0.05, ClickParameters(), noise_dbfs=-90, seed=0)
    assert len(detect_clicks(x, fs, DetectionSettings(min_interval_s=0.1)).events) == 1
    assert (
        len(
            detect_clicks(
                x, fs, DetectionSettings(min_interval_s=0.04, max_half_width_s=0.02)
            ).events
        )
        == 2
    )


def test_beating_dip_is_bridged_but_echo_is_not() -> None:
    fs = 96000
    click = ClickParameters(duration_ms=1.0, onset_ms=0.2, amplitude=0.5)
    main, _ = click_train(fs, 1, 1.0, click, start_s=0.05, tail_s=0.05)
    # A second burst 1.5 ms later (after a short dip) is part of the click...
    later = np.roll(main, round(0.0015 * fs)) * 0.6
    det = detect_clicks(main + later, fs)
    f = measure_click(main + later, fs, det.events[0], det.envelope, det.noise_floor)
    assert f.duration_ms > 2.0
    # ...but an echo 6 ms later (a wall at about 1 m) is not.
    echo = np.roll(main, round(0.006 * fs)) * 0.6
    det = detect_clicks(main + echo, fs)
    f = measure_click(main + echo, fs, det.events[0], det.envelope, det.noise_floor)
    assert f.duration_ms == pytest.approx(1.0, rel=0.1)


def test_long_sound_is_truncated() -> None:
    fs = 48000
    t = np.arange(fs) / fs
    x = np.where((t > 0.4) & (t < 0.6), 0.3 * np.sin(2 * np.pi * 1000 * t), 0.0)
    x = x + np.random.default_rng(0).normal(0, 1e-4, fs)
    det = detect_clicks(x, fs)
    assert det.events
    assert all(e.truncated for e in det.events)


def test_click_at_recording_edge_is_not_truncated() -> None:
    fs = 48000
    x, _ = click_train(fs, 1, 1.0, ClickParameters(), start_s=0.0, tail_s=0.0)
    det = detect_clicks(x, fs)
    assert len(det.events) == 1
    assert not det.events[0].truncated


def test_clipping_detected_in_raw_channels() -> None:
    fs = 48000
    x, _ = click_train(fs, 2, 0.3, ClickParameters(amplitude=1.0), noise_dbfs=-80, seed=0)
    stereo = np.column_stack([np.clip(1.4 * x, -1, 1), np.zeros_like(x)])
    mono = stereo.mean(axis=1)
    det = detect_clicks(mono, fs)
    f = measure_click(mono, fs, det.events[0], det.envelope, det.noise_floor, raw_channels=stereo)
    assert f.clipped
    g = measure_click(mono, fs, det.events[0], det.envelope, det.noise_floor)
    assert not g.clipped  # averaging with a silent channel hides it: why raw_channels exists


def test_spectral_measures_handle_degenerate_band() -> None:
    fs = 48000
    x, _ = click_train(fs, 1, 1.0, ClickParameters(), noise_dbfs=-80, seed=0)
    det = detect_clicks(x, fs)
    f = measure_click(x, fs, det.events[0], det.envelope, det.noise_floor, min_frequency_hz=1e9)
    assert np.isnan(f.peak_frequency_hz)
    assert np.isnan(f.bandwidth_hz)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_interval_s": 0.0},
        {"min_snr_db": -1.0},
        {"max_half_width_s": 0.5},
        {"max_gap_s": 0.05},
        {"max_gap_s": -0.001},
    ],
)
def test_invalid_settings(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="must"):
        DetectionSettings(**kwargs)


@pytest.mark.parametrize("x", [np.zeros(1), np.zeros((4, 2))])
def test_detect_rejects_bad_shapes(x: np.ndarray) -> None:
    with pytest.raises(ValueError, match="1-D"):
        detect_clicks(x, 48000)
