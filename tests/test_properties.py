# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Property-based tests: invariances the analysis must respect for any valid click."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from soundsight.audio import from_array
from soundsight.click.analysis import analyze_recording
from soundsight.click.synth import ClickParameters, click_train

FS = 48000

click_params = st.builds(
    ClickParameters,
    peak_frequency_hz=st.floats(1500.0, 6000.0),
    duration_ms=st.floats(1.5, 6.0),
    onset_ms=st.floats(0.1, 0.5),
    amplitude=st.just(0.25),
)


def _summary(x: np.ndarray):  # type: ignore[no-untyped-def]
    return analyze_recording(from_array(x, FS)).summary


@given(params=click_params, gain_db=st.floats(-30.0, 9.0), seed=st.integers(0, 2**16))
def test_gain_changes_level_only(params: ClickParameters, gain_db: float, seed: int) -> None:
    x, _ = click_train(FS, 5, 0.25, params, noise_dbfs=-75, seed=seed)
    base = _summary(x)
    scaled = _summary(x * 10 ** (gain_db / 20))
    assert scaled.n_clicks == base.n_clicks == 5
    assert scaled.median_duration_ms == pytest.approx(base.median_duration_ms, rel=1e-6)
    assert scaled.median_peak_frequency_hz == pytest.approx(base.median_peak_frequency_hz, rel=1e-6)
    assert scaled.median_peak_dbfs == pytest.approx(base.median_peak_dbfs + gain_db, abs=1e-6)


@given(params=click_params, shift_ms=st.floats(0.0, 300.0), seed=st.integers(0, 2**16))
def test_time_shift_changes_times_only(params: ClickParameters, shift_ms: float, seed: int) -> None:
    x, _ = click_train(FS, 5, 0.25, params, noise_dbfs=-75, seed=seed)
    pad = round(shift_ms / 1000 * FS)
    rng = np.random.default_rng(seed + 1)
    shifted = np.concatenate([rng.normal(0, 10 ** (-75 / 20), pad), x])
    a = analyze_recording(from_array(x, FS))
    b = analyze_recording(from_array(shifted, FS))
    assert b.summary.n_clicks == a.summary.n_clicks
    for ca, cb in zip(a.clicks, b.clicks, strict=True):
        # One sample of jitter: the Hilbert transform's length changes with the padding.
        assert cb.time_s - ca.time_s == pytest.approx(pad / FS, abs=1.0 / FS + 1e-9)
        assert cb.duration_ms == pytest.approx(ca.duration_ms, rel=0.05)
        assert cb.peak_frequency_hz == pytest.approx(ca.peak_frequency_hz, rel=0.01)


@given(params=click_params, seed=st.integers(0, 2**16))
def test_polarity_does_not_matter(params: ClickParameters, seed: int) -> None:
    x, _ = click_train(FS, 5, 0.25, params, noise_dbfs=-75, seed=seed)
    a, b = _summary(x), _summary(-x)
    assert a.median_duration_ms == pytest.approx(b.median_duration_ms)
    assert a.median_peak_frequency_hz == pytest.approx(b.median_peak_frequency_hz)
    assert a.median_peak_dbfs == pytest.approx(b.median_peak_dbfs)
