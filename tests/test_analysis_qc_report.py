# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for session analysis, quality checks and reports."""

from __future__ import annotations

import json

import numpy as np
import pytest

from soundsight.audio import AudioError, Recording, from_array
from soundsight.click.analysis import analyze_recording, summarize
from soundsight.click.qc import PROVISIONAL_PROFILE, Finding, Level, ReferenceProfile, assess
from soundsight.click.report import SCHEMA, _finite, format_text, to_dict
from soundsight.click.synth import ClickParameters, click_train

FS = 48000


def _analysis(n: int = 8, params: ClickParameters | None = None, noise: float = -70, **kw: float):  # type: ignore[no-untyped-def]
    x, _ = click_train(FS, n, 0.5, params or ClickParameters(), noise_dbfs=noise, seed=4, **kw)
    return analyze_recording(from_array(x, FS))


def _codes(findings: list[Finding], level: Level) -> set[str]:
    return {f.code for f in findings if f.level is level}


def test_good_session_passes_everything() -> None:
    findings = assess(_analysis())
    assert _codes(findings, Level.PASS) == {
        "duration",
        "peak-frequency",
        "background-noise",
        "consistency",
    }
    assert not _codes(findings, Level.WARN) | _codes(findings, Level.FAIL)


def test_summary_statistics() -> None:
    s = _analysis(n=6).summary
    assert s.n_clicks == 6
    assert s.median_interval_s == pytest.approx(0.5, abs=1e-4)
    assert s.cv_duration == pytest.approx(0.0, abs=0.01)
    assert s.level_sd_db == pytest.approx(0.0, abs=0.05)


def test_empty_summary() -> None:
    s = summarize(())
    assert s.n_clicks == 0
    assert s.median_duration_ms is None
    assert s.cv_duration is None


def test_single_click_summary_has_no_spread() -> None:
    s = _analysis(n=1).summary
    assert s.n_clicks == 1
    assert s.median_interval_s is None
    assert s.cv_peak_frequency is None


def test_no_clicks_fails() -> None:
    findings = assess(analyze_recording(from_array(np.zeros(FS), FS)))
    assert [f.code for f in findings] == ["no-clicks"]
    assert findings[0].level is Level.FAIL


def test_clipping_fails_first() -> None:
    x, _ = click_train(FS, 6, 0.5, ClickParameters(amplitude=1.0), noise_dbfs=-70, seed=0)
    findings = assess(analyze_recording(from_array(np.clip(1.5 * x, -1, 1), FS)))
    assert findings[0].code == "clipping"
    assert findings[0].level is Level.FAIL


def test_few_clicks_warns_and_skips_consistency() -> None:
    findings = assess(_analysis(n=3))
    assert "few-clicks" in _codes(findings, Level.WARN)
    assert "consistency" not in {f.code for f in findings}


def test_out_of_range_click_warns() -> None:
    params = ClickParameters(peak_frequency_hz=800.0, duration_ms=8.0)
    findings = assess(_analysis(params=params))
    assert {"duration", "peak-frequency"} <= _codes(findings, Level.WARN)


def test_noisy_recording_warns() -> None:
    findings = assess(_analysis(noise=-35, params=ClickParameters(amplitude=0.5)))
    assert "background-noise" in _codes(findings, Level.WARN)


def test_inconsistent_levels_warn() -> None:
    findings = assess(_analysis(n=10, level_jitter_db=8.0))
    assert "consistency" in _codes(findings, Level.WARN)


def test_long_sounds_warn() -> None:
    t = np.arange(2 * FS) / FS
    x = np.where((t > 0.5) & (t < 0.7), 0.3 * np.sin(2 * np.pi * 2500 * t), 0.0)
    x = x + np.random.default_rng(0).normal(0, 1e-4, x.size)
    findings = assess(analyze_recording(from_array(x, FS)))
    assert "long-sounds" in _codes(findings, Level.WARN)


def test_custom_profile_is_respected() -> None:
    strict = ReferenceProfile(name="strict", peak_frequency_hz=(3500.0, 4000.0))
    findings = assess(_analysis(), strict)
    assert "peak-frequency" in _codes(findings, Level.WARN)


def test_low_sample_rate_rejected() -> None:
    with pytest.raises(AudioError, match="too low"):
        analyze_recording(from_array(np.zeros(8000), 8000))


def test_too_short_recording_rejected() -> None:
    with pytest.raises(AudioError, match="too short"):
        analyze_recording(from_array(np.zeros(1), FS))


def test_channel_choice() -> None:
    x, _ = click_train(FS, 5, 0.3, ClickParameters(), noise_dbfs=-70, seed=0)
    noise = np.random.default_rng(1).normal(0, 1e-4, x.size)
    rec = Recording(np.column_stack([noise, x]), FS)
    assert analyze_recording(rec, channel=1).summary.n_clicks == 5
    assert analyze_recording(rec, channel=0).summary.n_clicks == 0


def test_text_report_is_linear_ascii() -> None:
    analysis = _analysis()
    text = format_text(
        analysis, assess(analysis), PROVISIONAL_PROFILE, source="x.wav", verbose=True
    )
    assert text.isascii()
    assert "Clicks found: 8." in text
    assert "single channel" in text
    assert "Click 8 at" in text
    assert text.endswith("Result: 0 failures, 0 warnings.\n")
    assert "|" not in text


def test_text_report_channel_wording() -> None:
    x, _ = click_train(FS, 5, 0.3, ClickParameters(), noise_dbfs=-70, seed=0)
    rec = Recording(np.column_stack([x, x]), FS)
    for channel, wording in (("mean", "average of 2 channels"), (1, "channel 1 of 2")):
        analysis = analyze_recording(rec, channel=channel)  # type: ignore[arg-type]
        assert wording in format_text(analysis, [], PROVISIONAL_PROFILE)


def test_text_report_flags_and_plurals() -> None:
    x, _ = click_train(FS, 6, 0.5, ClickParameters(amplitude=1.0), noise_dbfs=-70, seed=0)
    analysis = analyze_recording(from_array(np.clip(1.5 * x, -1, 1), FS))
    text = format_text(analysis, assess(analysis), PROVISIONAL_PROFILE, verbose=True)
    assert ", clipped." in text
    assert "1 failure," in text


def test_text_report_without_clicks() -> None:
    analysis = analyze_recording(from_array(np.zeros(FS), FS))
    text = format_text(analysis, assess(analysis), PROVISIONAL_PROFILE)
    assert "Typical click" not in text
    assert "Background noise level: unknown" not in text


def test_json_report_round_trips_without_nan() -> None:
    analysis = analyze_recording(from_array(np.zeros(FS), FS))
    data = to_dict(analysis, assess(analysis), PROVISIONAL_PROFILE, source="silence.wav")
    encoded = json.dumps(data, allow_nan=False)
    decoded = json.loads(encoded)
    assert decoded["schema"] == SCHEMA
    assert decoded["findings"][0]["code"] == "no-clicks"
    assert decoded["analysis"]["summary"]["median_duration_ms"] is None


def test_json_report_replaces_nan_and_inf() -> None:
    analysis = _analysis(n=5)
    data = to_dict(analysis, [], PROVISIONAL_PROFILE)
    data["extra"] = [float("nan"), float("-inf"), 1.0]
    assert _finite(data["extra"]) == [None, None, 1.0]
