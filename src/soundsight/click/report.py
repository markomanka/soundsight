# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Reports of a click analysis, as linear text and as JSON-ready data.

The text report is meant to be read by a screen reader: one fact per line, no tables
or box-drawing characters, units spelled out, plain ASCII.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, cast

from soundsight import __version__
from soundsight.click.analysis import ClickAnalysis
from soundsight.click.qc import Finding, Level, ReferenceProfile

SCHEMA = "soundsight.click-report/1"


def format_text(
    analysis: ClickAnalysis,
    findings: list[Finding],
    profile: ReferenceProfile,
    *,
    source: str | None = None,
    verbose: bool = False,
) -> str:
    """Render the analysis and findings as plain, linear text."""
    s = analysis.summary
    if analysis.n_channels == 1:
        channel = "single channel"
    elif analysis.channel == "mean":
        channel = f"average of {analysis.n_channels} channels"
    else:
        channel = f"channel {analysis.channel} of {analysis.n_channels}"
    lines = ["SoundSight click analysis"]
    if source:
        lines.append(f"File: {source}")
    lines += [
        f"Length {analysis.duration_s:.1f} seconds, sample rate {analysis.sample_rate} hertz, "
        f"{channel}.",
        f"Background noise level: {_db(analysis.noise_floor_dbfs)} decibels full scale.",
        f"Clicks found: {s.n_clicks}.",
    ]
    if s.n_clicks:
        lines.append(
            f"Typical click: {s.median_duration_ms:.1f} milliseconds long, peak frequency "
            f"{s.median_peak_frequency_hz:.0f} hertz, level {_db(s.median_peak_dbfs)} decibels "
            "full scale."
        )
    if verbose:
        for i, c in enumerate(analysis.clicks, start=1):
            flags = "".join(
                (", clipped" if c.clipped else "", ", longer than a click" if c.truncated else "")
            )
            lines.append(
                f"Click {i} at {c.time_s:.2f} seconds: {c.duration_ms:.1f} milliseconds, "
                f"{c.peak_frequency_hz:.0f} hertz, {_db(c.peak_dbfs)} decibels full scale, "
                f"{c.snr_db:.0f} decibels above noise{flags}."
            )
    lines.append(f"Checks against the {profile.name} reference profile:")
    lines += [f"{f.level.value.upper()}: {f.message}" for f in findings]
    n_fail = sum(f.level is Level.FAIL for f in findings)
    n_warn = sum(f.level is Level.WARN for f in findings)
    lines.append(f"Result: {_plural(n_fail, 'failure')}, {_plural(n_warn, 'warning')}.")
    return "\n".join(lines) + "\n"


def to_dict(
    analysis: ClickAnalysis,
    findings: list[Finding],
    profile: ReferenceProfile,
    *,
    source: str | None = None,
) -> dict[str, Any]:
    """Return the analysis as plain data that :func:`json.dumps` accepts (no NaN)."""
    data = {
        "schema": SCHEMA,
        "soundsight_version": __version__,
        "source": source,
        "profile": asdict(profile),
        "analysis": asdict(analysis),
        "findings": [
            {"level": f.level.value, "code": f.code, "message": f.message} for f in findings
        ],
    }
    return cast(dict[str, Any], _finite(data))


def _finite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_finite(v) for v in value]
    return value


def _db(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "unknown"
    return f"{value:.0f}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"
