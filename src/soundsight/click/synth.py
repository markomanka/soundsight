# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
r"""Synthetic tongue clicks with exactly known properties.

The model is deliberately simple: a sinusoid at the peak frequency under an envelope
that rises with a raised-cosine onset and then decays exponentially,

.. math::

    x(t) = A\,e(t)\,\sin(2\pi f t), \qquad
    e(t) = \begin{cases}
        \tfrac12\left(1 - \cos(\pi t / t_\mathrm{on})\right) & 0 \le t < t_\mathrm{on} \\
        \exp\!\left(-(t - t_\mathrm{on}) / \tau\right) & t \ge t_\mathrm{on}
    \end{cases}

The decay constant :math:`\tau` is chosen so that the envelope stays above -20 dB of its
maximum for exactly ``duration_ms``, which is how :mod:`soundsight.click.features`
defines click duration. That makes these clicks ground truth for testing the analysis.

This is a test signal and a neutral default stimulus, not a model of any particular
echolocator. The defaults (3 ms, 3 kHz) sit within the ranges reported for expert
clicks in the literature: durations of a few milliseconds, peak energy around 2-4 kHz.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from soundsight.audio import FloatArray

#: Envelope level that defines the extent (duration) of a click: -20 dB.
BOUNDARY_LEVEL = 0.1
#: Level at which a synthesized click is cut off: -60 dB.
TAIL_LEVEL = 1e-3
#: Fraction of the onset spent below BOUNDARY_LEVEL: acos(1 - 2*0.1) / pi.
_ONSET_FRACTION_BELOW = math.acos(1.0 - 2.0 * BOUNDARY_LEVEL) / math.pi


@dataclass(frozen=True)
class ClickParameters:
    """Parameters of a synthetic click.

    Parameters
    ----------
    peak_frequency_hz
        Frequency of the carrier, which is the spectral peak.
    duration_ms
        Time the envelope spends above -20 dB of its maximum.
    onset_ms
        Rise time from silence to the envelope maximum.
    amplitude
        Envelope maximum, with full scale at 1.0.
    """

    peak_frequency_hz: float = 3000.0
    duration_ms: float = 3.0
    onset_ms: float = 0.3
    amplitude: float = 0.5

    def __post_init__(self) -> None:
        """Check that the parameters describe a realisable click."""
        if not self.peak_frequency_hz > 0:
            msg = f"peak_frequency_hz must be positive, got {self.peak_frequency_hz}"
            raise ValueError(msg)
        if not self.onset_ms > 0:
            msg = f"onset_ms must be positive, got {self.onset_ms}"
            raise ValueError(msg)
        if not self.duration_ms > self.onset_ms * (1.0 - _ONSET_FRACTION_BELOW):
            msg = (
                f"duration_ms ({self.duration_ms}) is too short for onset_ms "
                f"({self.onset_ms}); it must exceed "
                f"{self.onset_ms * (1.0 - _ONSET_FRACTION_BELOW):.3f}"
            )
            raise ValueError(msg)
        if not 0 < self.amplitude <= 1:
            msg = f"amplitude must be in (0, 1], got {self.amplitude}"
            raise ValueError(msg)

    @property
    def decay_time_constant_s(self) -> float:
        """Exponential decay constant tau, in seconds."""
        onset_s = self.onset_ms / 1000.0
        above_in_onset_s = onset_s * (1.0 - _ONSET_FRACTION_BELOW)
        return (self.duration_ms / 1000.0 - above_in_onset_s) / math.log(1.0 / BOUNDARY_LEVEL)

    @property
    def length_s(self) -> float:
        """Total length of the synthesized click, cut off at -60 dB."""
        return self.onset_ms / 1000.0 + self.decay_time_constant_s * math.log(1.0 / TAIL_LEVEL)


def envelope(t: FloatArray, params: ClickParameters) -> FloatArray:
    """Evaluate the click envelope (maximum 1.0) at times ``t`` in seconds."""
    onset_s = params.onset_ms / 1000.0
    tau = params.decay_time_constant_s
    t = np.asarray(t, dtype=np.float64)
    rising = 0.5 * (1.0 - np.cos(np.pi * np.clip(t, 0.0, onset_s) / onset_s))
    decaying = np.exp(-np.maximum(t - onset_s, 0.0) / tau)
    out = np.where(t < onset_s, rising, decaying)
    return np.asarray(np.where(t < 0.0, 0.0, out), dtype=np.float64)


def synth_click(sample_rate: int, params: ClickParameters | None = None) -> FloatArray:
    """Synthesize a single click.

    Returns a 1-D array starting at the beginning of the onset and ending when the
    envelope has decayed to -60 dB.
    """
    if sample_rate <= 0:
        msg = f"sample_rate must be positive, got {sample_rate}"
        raise ValueError(msg)
    params = params or ClickParameters()
    if params.peak_frequency_hz >= sample_rate / 2:
        msg = (
            f"peak_frequency_hz ({params.peak_frequency_hz}) must be below the Nyquist "
            f"frequency ({sample_rate / 2})"
        )
        raise ValueError(msg)
    n = max(2, math.ceil(params.length_s * sample_rate))
    t = np.arange(n, dtype=np.float64) / sample_rate
    carrier = np.sin(2.0 * np.pi * params.peak_frequency_hz * t)
    return np.asarray(params.amplitude * envelope(t, params) * carrier, dtype=np.float64)


def click_train(
    sample_rate: int,
    n_clicks: int,
    interval_s: float,
    params: ClickParameters | None = None,
    *,
    start_s: float = 0.1,
    tail_s: float = 0.1,
    noise_dbfs: float | None = None,
    level_jitter_db: float = 0.0,
    seed: int | None = None,
) -> tuple[FloatArray, FloatArray]:
    """Synthesize a sequence of clicks, optionally in Gaussian background noise.

    Parameters
    ----------
    sample_rate
        Sampling rate in hertz.
    n_clicks
        Number of clicks.
    interval_s
        Time between successive clicks.
    params
        Click parameters (shared by all clicks).
    start_s, tail_s
        Silence (or noise) before the first and after the last click.
    noise_dbfs
        RMS level of white background noise, or ``None`` for none.
    level_jitter_db
        Standard deviation of random per-click level changes.
    seed
        Seed for the random generator, for reproducible signals.

    Returns
    -------
    signal, peak_times_s
        The 1-D signal and the time of each click's envelope maximum.
    """
    if n_clicks < 0:
        msg = f"n_clicks must be non-negative, got {n_clicks}"
        raise ValueError(msg)
    if not interval_s > 0:
        msg = f"interval_s must be positive, got {interval_s}"
        raise ValueError(msg)
    params = params or ClickParameters()
    click = synth_click(sample_rate, params)
    rng = np.random.default_rng(seed)
    starts = [round((start_s + i * interval_s) * sample_rate) for i in range(n_clicks)]
    last_end = starts[-1] + click.size if starts else round(start_s * sample_rate)
    signal = np.zeros(last_end + round(tail_s * sample_rate), dtype=np.float64)
    for start in starts:
        gain = 10.0 ** (rng.normal(0.0, level_jitter_db) / 20.0) if level_jitter_db else 1.0
        signal[start : start + click.size] += gain * click
    if noise_dbfs is not None:
        signal += rng.normal(0.0, 10.0 ** (noise_dbfs / 20.0), signal.size)
    peak_offset_s = params.onset_ms / 1000.0
    peak_times = np.array([s / sample_rate + peak_offset_s for s in starts], dtype=np.float64)
    return signal, peak_times
