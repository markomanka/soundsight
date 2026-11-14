# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Analysis of a whole click recording: detection, measurement and summary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from soundsight.audio import AudioError, Recording, dbfs
from soundsight.click.detect import DetectionSettings, detect_clicks
from soundsight.click.features import ClickFeatures, measure_click

#: Below this rate the 2-5 kHz region where click energy lives is not captured reliably.
MIN_SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class SessionSummary:
    """Summary statistics over all clicks in a recording.

    Medians are robust to the odd bad click. The coefficient of variation (standard
    deviation divided by mean) measures consistency; it needs at least two clicks and
    is ``None`` otherwise, as are all statistics when no click was found.
    """

    n_clicks: int
    median_interval_s: float | None
    median_duration_ms: float | None
    median_peak_frequency_hz: float | None
    median_peak_dbfs: float | None
    median_snr_db: float | None
    cv_duration: float | None
    cv_peak_frequency: float | None
    level_sd_db: float | None
    n_clipped: int
    n_truncated: int


@dataclass(frozen=True)
class ClickAnalysis:
    """Complete result of analysing one recording."""

    sample_rate: int
    duration_s: float
    n_channels: int
    channel: int | Literal["mean"]
    noise_floor_dbfs: float
    clicks: tuple[ClickFeatures, ...]
    summary: SessionSummary


def analyze_recording(
    recording: Recording,
    *,
    channel: int | Literal["mean"] = "mean",
    settings: DetectionSettings | None = None,
) -> ClickAnalysis:
    """Detect and measure every click in ``recording``.

    Parameters
    ----------
    recording
        The recording to analyse.
    channel
        Channel index to analyse, or ``"mean"`` to average all channels.
    settings
        Detector tuning.
    """
    if recording.sample_rate < MIN_SAMPLE_RATE:
        msg = (
            f"sample rate {recording.sample_rate} Hz is too low for click analysis; "
            f"record at {MIN_SAMPLE_RATE} Hz or more (44100 or 48000 Hz recommended)"
        )
        raise AudioError(msg)
    x = recording.channel(channel)
    if x.size < 2:  # noqa: PLR2004
        msg = "recording is too short to analyse"
        raise AudioError(msg)
    detection = detect_clicks(x, recording.sample_rate, settings)
    raw = recording.samples if channel == "mean" else recording.samples[:, [channel]]
    clicks = tuple(
        measure_click(
            x,
            recording.sample_rate,
            event,
            detection.envelope,
            detection.noise_floor,
            raw_channels=raw,
        )
        for event in detection.events
    )
    return ClickAnalysis(
        sample_rate=recording.sample_rate,
        duration_s=recording.duration_s,
        n_channels=recording.n_channels,
        channel=channel,
        noise_floor_dbfs=dbfs(detection.noise_floor),
        clicks=clicks,
        summary=summarize(clicks),
    )


def summarize(clicks: tuple[ClickFeatures, ...]) -> SessionSummary:
    """Compute :class:`SessionSummary` statistics for a sequence of clicks."""
    n = len(clicks)
    n_clipped = sum(c.clipped for c in clicks)
    n_truncated = sum(c.truncated for c in clicks)
    if n == 0:
        return SessionSummary(0, None, None, None, None, None, None, None, None, 0, 0)

    times = np.array([c.time_s for c in clicks])
    durations = np.array([c.duration_ms for c in clicks])
    freqs = np.array([c.peak_frequency_hz for c in clicks])
    levels = np.array([c.peak_dbfs for c in clicks])
    snrs = np.array([c.snr_db for c in clicks])
    several = n >= 2  # noqa: PLR2004
    return SessionSummary(
        n_clicks=n,
        median_interval_s=float(np.median(np.diff(times))) if several else None,
        median_duration_ms=float(np.median(durations)),
        median_peak_frequency_hz=float(np.median(freqs)),
        median_peak_dbfs=float(np.median(levels)),
        median_snr_db=float(np.median(snrs)),
        cv_duration=_cv(durations) if several else None,
        cv_peak_frequency=_cv(freqs) if several else None,
        level_sd_db=float(np.std(levels, ddof=1)) if several else None,
        n_clipped=int(n_clipped),
        n_truncated=int(n_truncated),
    )


def _cv(values: NDArray[np.float64]) -> float:
    return float(np.std(values, ddof=1) / np.mean(values))
