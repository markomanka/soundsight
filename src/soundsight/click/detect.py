# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Finding clicks in a recording.

Detection works on the amplitude envelope (magnitude of the analytic signal). The
background noise floor is estimated as the median of the envelope, which is robust
because clicks occupy a tiny fraction of a recording (a few milliseconds per second).
A peak counts as a click when it is both well above the noise floor and not too far
below the loudest click, which rejects breaths, rustles and room echoes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy import fft, signal

from soundsight.audio import FloatArray

#: Floor used when the input is digital silence, to keep levels finite (-200 dBFS).
_MIN_NOISE_FLOOR = 1e-10


@dataclass(frozen=True)
class DetectionSettings:
    """Tuning of the click detector.

    Parameters
    ----------
    min_interval_s
        Minimum time between two clicks; closer peaks are merged into the louder one.
    min_snr_db
        Minimum level of a click above the noise floor.
    max_level_spread_db
        Peaks more than this far below the loudest click are ignored.
    boundary_db
        A click's extent runs until its envelope falls this far below its peak.
    max_gap_s
        Dips below the boundary level shorter than this are bridged. Real clicks have
        several spectral components whose beating makes brief envelope nulls; echoes
        from surfaces more than about 20 cm away arrive after a longer silent gap.
    max_half_width_s
        How far either side of a peak to look for the click's boundaries.
    """

    min_interval_s: float = 0.1
    min_snr_db: float = 20.0
    max_level_spread_db: float = 30.0
    boundary_db: float = 20.0
    max_gap_s: float = 0.001
    max_half_width_s: float = 0.02

    def __post_init__(self) -> None:
        """Reject settings that cannot work."""
        for name in ("min_interval_s", "min_snr_db", "max_level_spread_db", "boundary_db"):
            if not getattr(self, name) > 0:
                msg = f"{name} must be positive, got {getattr(self, name)}"
                raise ValueError(msg)
        if not 0 < self.max_half_width_s <= self.min_interval_s:
            msg = "max_half_width_s must be positive and no larger than min_interval_s"
            raise ValueError(msg)
        if not 0 <= self.max_gap_s < self.max_half_width_s:
            msg = "max_gap_s must be non-negative and smaller than max_half_width_s"
            raise ValueError(msg)


@dataclass(frozen=True)
class ClickEvent:
    """Location of one click, as sample indices into the analysed signal.

    ``start_index`` is the first and ``end_index`` the last sample whose envelope is
    within ``boundary_db`` of the peak, bridging dips shorter than ``max_gap_s``.
    ``truncated`` is true when the sound had not ended inside the search window,
    meaning it is longer than a click should be.
    """

    peak_index: int
    start_index: int
    end_index: int
    truncated: bool


@dataclass(frozen=True)
class Detection:
    """Result of running the detector on one signal."""

    events: tuple[ClickEvent, ...]
    envelope: FloatArray
    noise_floor: float
    threshold: float


def amplitude_envelope(x: FloatArray) -> FloatArray:
    """Return the magnitude of the analytic signal of ``x``."""
    n = x.size
    analytic = signal.hilbert(x, N=fft.next_fast_len(n, real=True))[:n]
    return np.asarray(np.abs(analytic), dtype=np.float64)


def detect_clicks(
    x: FloatArray, sample_rate: int, settings: DetectionSettings | None = None
) -> Detection:
    """Detect clicks in a 1-D signal.

    Parameters
    ----------
    x
        The signal, full scale 1.0.
    sample_rate
        Sampling rate in hertz.
    settings
        Detector tuning; defaults to :class:`DetectionSettings`.
    """
    settings = settings or DetectionSettings()
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1 or x.size < 2:  # noqa: PLR2004 - Hilbert transform needs two samples
        msg = "detect_clicks needs a 1-D signal with at least two samples"
        raise ValueError(msg)
    env = amplitude_envelope(x)
    noise_floor = max(float(np.median(env)), _MIN_NOISE_FLOOR)
    loudest = float(env.max())
    threshold = max(
        noise_floor * 10.0 ** (settings.min_snr_db / 20.0),
        loudest * 10.0 ** (-settings.max_level_spread_db / 20.0),
    )
    if loudest < threshold:
        return Detection((), env, noise_floor, threshold)

    distance = max(1, round(settings.min_interval_s * sample_rate))
    peaks, _ = signal.find_peaks(env, height=threshold, distance=distance)
    half_width = max(1, round(settings.max_half_width_s * sample_rate))
    gap = round(settings.max_gap_s * sample_rate)
    ratio = 10.0 ** (-settings.boundary_db / 20.0)
    events = tuple(_bounds(env, int(p), half_width, gap, ratio) for p in peaks)
    return Detection(events, env, noise_floor, threshold)


def _bounds(env: FloatArray, peak: int, half_width: int, gap: int, ratio: float) -> ClickEvent:
    level = env[peak] * ratio
    lo = max(0, peak - half_width)
    hi = min(env.size - 1, peak + half_width)
    end, open_right = _extent(env[peak : hi + 1] >= level, gap)
    start, open_left = _extent(env[lo : peak + 1][::-1] >= level, gap)
    return ClickEvent(
        peak_index=peak,
        start_index=peak - start,
        end_index=peak + end,
        truncated=(open_right and hi < env.size - 1) or (open_left and lo > 0),
    )


def _extent(above: npt.NDArray[np.bool_], gap: int) -> tuple[int, bool]:
    """Walk outwards from index 0 of ``above`` (which is True) across gaps up to ``gap``.

    Returns the offset of the last sample of the extent, and whether the extent was still
    open (no gap longer than ``gap`` confirmed) when the window ended.
    """
    idx = np.flatnonzero(above)
    jumps = np.flatnonzero(np.diff(idx) > gap + 1)
    last = int(idx[jumps[0]]) if jumps.size else int(idx[-1])
    still_open = jumps.size == 0 and above.size - 1 - last <= gap
    return last, still_open
