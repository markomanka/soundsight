# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Regression test on the real 2016 click recording from the original demonstrator.

The file is not redistributed with this repository (it has no license). CI downloads it
from the original repository, pinned to a commit and checked against a SHA-256 digest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from soundsight.audio import read_wav
from soundsight.click.analysis import analyze_recording
from soundsight.click.qc import Level, assess

pytestmark = pytest.mark.legacy


def test_legacy_recording_summary(legacy_click: Path) -> None:
    rec = read_wav(legacy_click)
    assert rec.sample_rate == 192000
    assert rec.n_channels == 2
    analysis = analyze_recording(rec)
    s = analysis.summary
    assert s.n_clicks == 9
    assert s.median_interval_s == pytest.approx(1.28, abs=0.05)
    assert s.median_duration_ms is not None
    assert 1.5 <= s.median_duration_ms <= 3.0
    assert s.median_peak_frequency_hz is not None
    assert 2400 <= s.median_peak_frequency_hz <= 3100
    assert s.median_snr_db is not None
    assert s.median_snr_db > 60
    assert s.n_clipped == 0
    assert not any(f.level is Level.FAIL for f in assess(analysis))
