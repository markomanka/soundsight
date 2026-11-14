# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Quality checks on a click recording, against a reference profile.

Each check yields a :class:`Finding` with a stable ``code`` (for translations and for
software that consumes reports) and a plain-language message written to be read
aloud by a screen reader.

The default profile is PROVISIONAL. Its ranges loosely follow published descriptions
of expert echolocators' clicks and must be calibrated with echolocation instructors
and researchers before being presented to trainees as targets.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from soundsight.click.analysis import ClickAnalysis


class Level(enum.StrEnum):
    """Outcome of a check."""

    PASS = "pass"  # noqa: S105 - a check outcome, not a password
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class Finding:
    """Outcome of one quality check."""

    level: Level
    code: str
    message: str


@dataclass(frozen=True)
class ReferenceProfile:
    """Target ranges for a good, consistent click recording."""

    name: str
    duration_ms: tuple[float, float] = (1.0, 5.0)
    peak_frequency_hz: tuple[float, float] = (2000.0, 5000.0)
    min_snr_db: float = 30.0
    max_cv_duration: float = 0.25
    max_cv_peak_frequency: float = 0.10
    max_level_sd_db: float = 3.0
    min_clicks: int = 5


PROVISIONAL_PROFILE = ReferenceProfile(name="provisional-2026")


def assess(
    analysis: ClickAnalysis, profile: ReferenceProfile = PROVISIONAL_PROFILE
) -> list[Finding]:
    """Run all quality checks and return their findings, failures first."""
    s = analysis.summary
    if s.n_clicks == 0:
        return [
            Finding(
                Level.FAIL,
                "no-clicks",
                "No clicks were found. Check that the microphone is on and close enough, "
                "and click at least five times, about once per second.",
            )
        ]
    findings: list[Finding] = []
    if s.n_clipped:
        findings.append(
            Finding(
                Level.FAIL,
                "clipping",
                f"{s.n_clipped} of {s.n_clicks} clicks overloaded the recording. "
                "Lower the input gain or move the microphone further away, then record again.",
            )
        )
    if s.n_truncated:
        findings.append(
            Finding(
                Level.WARN,
                "long-sounds",
                f"{s.n_truncated} detected sounds were longer than a click should be. "
                "They may be speech, knocks or echoes in a reverberant room.",
            )
        )
    if s.n_clicks < profile.min_clicks:
        findings.append(
            Finding(
                Level.WARN,
                "few-clicks",
                f"Only {s.n_clicks} clicks were found; at least {profile.min_clicks} are "
                "needed to judge consistency.",
            )
        )
    findings.extend(_range_checks(analysis, profile))
    order = {Level.FAIL: 0, Level.WARN: 1, Level.PASS: 2}
    return sorted(findings, key=lambda f: order[f.level])


def _range_checks(analysis: ClickAnalysis, profile: ReferenceProfile) -> list[Finding]:
    s = analysis.summary
    out: list[Finding] = []
    assert s.median_duration_ms is not None  # noqa: S101 - guaranteed when n_clicks > 0
    assert s.median_peak_frequency_hz is not None  # noqa: S101
    assert s.median_snr_db is not None  # noqa: S101

    lo, hi = profile.duration_ms
    ok = lo <= s.median_duration_ms <= hi
    out.append(
        Finding(
            Level.PASS if ok else Level.WARN,
            "duration",
            f"Typical click duration is {s.median_duration_ms:.1f} milliseconds; "
            f"the reference range is {lo:g} to {hi:g}.",
        )
    )
    lo, hi = profile.peak_frequency_hz
    ok = lo <= s.median_peak_frequency_hz <= hi
    out.append(
        Finding(
            Level.PASS if ok else Level.WARN,
            "peak-frequency",
            f"Typical peak frequency is {s.median_peak_frequency_hz:.0f} hertz; "
            f"the reference range is {lo:g} to {hi:g}.",
        )
    )
    ok = s.median_snr_db >= profile.min_snr_db
    out.append(
        Finding(
            Level.PASS if ok else Level.WARN,
            "background-noise",
            f"Clicks are {s.median_snr_db:.0f} decibels above the background noise; "
            f"at least {profile.min_snr_db:g} is recommended."
            + ("" if ok else " Record in a quieter place."),
        )
    )
    if s.n_clicks >= profile.min_clicks:
        assert s.cv_duration is not None  # noqa: S101 - guaranteed when n_clicks >= 2
        assert s.cv_peak_frequency is not None  # noqa: S101
        assert s.level_sd_db is not None  # noqa: S101
        consistent = (
            s.cv_duration <= profile.max_cv_duration
            and s.cv_peak_frequency <= profile.max_cv_peak_frequency
            and s.level_sd_db <= profile.max_level_sd_db
        )
        out.append(
            Finding(
                Level.PASS if consistent else Level.WARN,
                "consistency",
                f"Duration varies by {100 * s.cv_duration:.0f} percent, peak frequency by "
                f"{100 * s.cv_peak_frequency:.0f} percent and level by {s.level_sd_db:.1f} "
                "decibels between clicks."
                + ("" if consistent else " Aim for clicks that sound the same every time."),
            )
        )
    return out
