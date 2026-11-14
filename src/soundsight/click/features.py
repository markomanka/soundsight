# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Measurements of individual clicks.

Definitions used throughout SoundSight:

duration
    Time from the first to the last sample where the amplitude envelope is within
    20 dB of its peak, bridging dips shorter than 1 ms (see
    :class:`soundsight.click.detect.DetectionSettings`).
peak level
    Envelope maximum in dB re full scale (dBFS).
peak frequency
    Frequency of the maximum of the click's power spectrum above ``min_frequency_hz``,
    refined by parabolic interpolation on the log spectrum.
spectral centroid
    Power-weighted mean frequency above ``min_frequency_hz``.
bandwidth
    Width of the contiguous band around the peak within 10 dB of the peak power.
signal-to-noise ratio
    Envelope peak relative to the recording's noise floor, in dB.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.signal import windows

from soundsight.audio import FloatArray, dbfs
from soundsight.click.detect import ClickEvent

#: Sample magnitude at or above which a sample counts as clipped.
CLIP_LEVEL = 0.999
#: Analysis margin added before and after the click's extent.
_MARGIN_S = 0.0005
_MIN_FFT = 8192


@dataclass(frozen=True)
class ClickFeatures:
    """Measured properties of one click (see module docstring for definitions)."""

    time_s: float
    peak_dbfs: float
    duration_ms: float
    peak_frequency_hz: float
    centroid_hz: float
    bandwidth_hz: float
    snr_db: float
    clipped: bool
    truncated: bool


def measure_click(
    x: FloatArray,
    sample_rate: int,
    event: ClickEvent,
    envelope: FloatArray,
    noise_floor: float,
    *,
    raw_channels: NDArray[np.float64] | None = None,
    min_frequency_hz: float = 200.0,
) -> ClickFeatures:
    """Measure one detected click.

    Parameters
    ----------
    x
        The 1-D signal the click was detected in.
    sample_rate
        Sampling rate in hertz.
    event
        The click's location, from :func:`soundsight.click.detect.detect_clicks`.
    envelope
        Amplitude envelope of ``x`` (from the same detection).
    noise_floor
        Noise floor of ``x`` (from the same detection).
    raw_channels
        Original multichannel samples, shape ``(n_frames, n_channels)``, used to detect
        clipping that averaging channels would hide. Defaults to ``x``.
    min_frequency_hz
        Spectral measurements ignore energy below this frequency (handling noise, hum).
    """
    margin = round(_MARGIN_S * sample_rate)
    lo = max(0, event.start_index - margin)
    hi = min(x.size, event.end_index + margin + 1)
    segment = x[lo:hi]

    raw = x[:, np.newaxis] if raw_channels is None else raw_channels
    clipped = bool(np.any(np.abs(raw[lo:hi]) >= CLIP_LEVEL))

    peak_amp = float(envelope[event.peak_index])
    freqs, power = _power_spectrum(segment, sample_rate)
    band = freqs >= min_frequency_hz
    peak_hz, bandwidth_hz, centroid_hz = _spectral_shape(freqs[band], power[band])

    return ClickFeatures(
        time_s=event.peak_index / sample_rate,
        peak_dbfs=dbfs(peak_amp),
        duration_ms=1000.0 * (event.end_index - event.start_index + 1) / sample_rate,
        peak_frequency_hz=peak_hz,
        centroid_hz=centroid_hz,
        bandwidth_hz=bandwidth_hz,
        snr_db=dbfs(peak_amp) - dbfs(noise_floor),
        clipped=clipped,
        truncated=event.truncated,
    )


def _power_spectrum(segment: FloatArray, sample_rate: int) -> tuple[FloatArray, FloatArray]:
    n = segment.size
    tapered = segment * windows.tukey(n, alpha=0.25)
    n_fft = max(_MIN_FFT, 1 << math.ceil(math.log2(4 * n)))
    power = np.abs(np.fft.rfft(tapered, n=n_fft)) ** 2
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    return freqs.astype(np.float64), power.astype(np.float64)


def _spectral_shape(freqs: FloatArray, power: FloatArray) -> tuple[float, float, float]:
    total = float(power.sum())
    if freqs.size < 3 or total <= 0.0:  # noqa: PLR2004 - interpolation needs neighbours
        return float("nan"), float("nan"), float("nan")
    k = int(np.argmax(power))
    peak_hz = float(freqs[k])
    if 0 < k < freqs.size - 1:
        a, b, c = np.log(power[k - 1 : k + 2] + total * 1e-30)
        denom = a - 2.0 * b + c
        if denom < 0.0:
            peak_hz += 0.5 * (a - c) / denom * float(freqs[1] - freqs[0])
    above = power >= power[k] / 10.0
    left = k
    while left > 0 and above[left - 1]:
        left -= 1
    right = k
    while right < freqs.size - 1 and above[right + 1]:
        right += 1
    bin_hz = float(freqs[1] - freqs[0])
    bandwidth = float(freqs[right] - freqs[left]) + bin_hz
    centroid = float((freqs * power).sum() / total)
    return peak_hz, bandwidth, centroid
