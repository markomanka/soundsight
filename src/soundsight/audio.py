# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Reading, writing and validating audio recordings.

All samples are handled as 64-bit floats with full scale at 1.0, in an array of
shape ``(n_frames, n_channels)``, whatever the format of the file they came from.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.io import wavfile

FloatArray = NDArray[np.float64]

#: Integer sample formats and the divisor that maps them to full scale 1.0.
#: scipy returns 24-bit PCM left-justified in int32, so one divisor covers both.
_INT_SCALE: dict[np.dtype[np.generic], float] = {
    np.dtype(np.int16): 2.0**15,
    np.dtype(np.int32): 2.0**31,
}


class AudioError(ValueError):
    """Raised when audio data or an audio file cannot be used."""


@dataclass(frozen=True)
class Recording:
    """An immutable multichannel recording.

    Parameters
    ----------
    samples
        Sample values with full scale at 1.0. A 1-D array is treated as mono.
    sample_rate
        Sampling rate in hertz.
    """

    samples: FloatArray
    sample_rate: int

    def __post_init__(self) -> None:
        """Validate and freeze the sample array."""
        data = np.array(self.samples, dtype=np.float64, copy=True)
        if data.ndim == 1:
            data = data[:, np.newaxis]
        if data.ndim != 2:  # noqa: PLR2004 - (frames, channels)
            msg = f"samples must be 1-D or 2-D, got {data.ndim} dimensions"
            raise AudioError(msg)
        if data.shape[0] == 0 or data.shape[1] == 0:
            msg = "recording is empty"
            raise AudioError(msg)
        if not np.all(np.isfinite(data)):
            msg = "recording contains NaN or infinite values"
            raise AudioError(msg)
        if isinstance(self.sample_rate, bool) or not isinstance(self.sample_rate, int | np.integer):
            msg = f"sample_rate must be an integer, got {type(self.sample_rate).__name__}"
            raise AudioError(msg)
        if self.sample_rate <= 0:
            msg = f"sample_rate must be positive, got {self.sample_rate}"
            raise AudioError(msg)
        data.setflags(write=False)
        object.__setattr__(self, "samples", data)
        object.__setattr__(self, "sample_rate", int(self.sample_rate))

    @property
    def n_frames(self) -> int:
        """Number of sample frames."""
        return int(self.samples.shape[0])

    @property
    def n_channels(self) -> int:
        """Number of channels."""
        return int(self.samples.shape[1])

    @property
    def duration_s(self) -> float:
        """Duration in seconds."""
        return self.n_frames / self.sample_rate

    def channel(self, which: int | Literal["mean"] = "mean") -> FloatArray:
        """Return one channel, or the mean of all channels, as a 1-D array.

        Parameters
        ----------
        which
            A channel index (0-based) or ``"mean"``.
        """
        if which == "mean":
            return np.asarray(self.samples.mean(axis=1), dtype=np.float64)
        if not 0 <= which < self.n_channels:
            msg = f"channel {which} does not exist; the recording has {self.n_channels}"
            raise AudioError(msg)
        return np.array(self.samples[:, which], dtype=np.float64)


def from_array(samples: ArrayLike, sample_rate: int) -> Recording:
    """Build a :class:`Recording` from any array-like of floats."""
    return Recording(np.asarray(samples, dtype=np.float64), sample_rate)


def read_wav(path: str | Path) -> Recording:
    """Read a WAV file into a :class:`Recording`.

    Supports 8-, 16-, 24- and 32-bit PCM and 32/64-bit float files.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    AudioError
        If the file is not a readable WAV file or holds unusable data.
    """
    path = Path(path)
    if not path.is_file():
        msg = f"no such file: {path}"
        raise FileNotFoundError(msg)
    try:
        with warnings.catch_warnings():
            # Metadata chunks (e.g. from recorders) are skipped by scipy with a warning.
            warnings.simplefilter("ignore", wavfile.WavFileWarning)
            sample_rate, raw = wavfile.read(path)
    except ValueError as exc:
        msg = f"cannot read {path.name} as a WAV file: {exc}"
        raise AudioError(msg) from exc
    return Recording(_to_float(np.asarray(raw)), int(sample_rate))


def _to_float(raw: NDArray[np.generic]) -> FloatArray:
    if raw.dtype == np.uint8:
        return (raw.astype(np.float64) - 128.0) / 128.0
    scale = _INT_SCALE.get(raw.dtype)
    if scale is not None:
        return raw.astype(np.float64) / scale
    if raw.dtype in (np.float32, np.float64):
        return raw.astype(np.float64)
    msg = f"unsupported sample format: {raw.dtype}"  # pragma: no cover - scipy rejects first
    raise AudioError(msg)  # pragma: no cover


def _as_pcm16(data: FloatArray) -> NDArray[np.int16]:
    return np.clip(np.round(data * 2.0**15), -(2**15), 2**15 - 1).astype(np.int16)


def _as_float32(data: FloatArray) -> NDArray[np.float32]:
    return data.astype(np.float32)


_Encoder = Callable[[FloatArray], NDArray[np.int16] | NDArray[np.float32]]
_ENCODERS: dict[str, _Encoder] = {"pcm16": _as_pcm16, "float32": _as_float32}


def write_wav(
    path: str | Path,
    recording: Recording,
    *,
    sample_format: Literal["pcm16", "float32"] = "pcm16",
) -> Path:
    """Write a :class:`Recording` to a WAV file and return its path.

    ``pcm16`` clips values outside full scale; ``float32`` stores them unchanged.
    """
    encode = _ENCODERS.get(sample_format)
    if encode is None:  # reachable from untyped callers
        msg = f"unknown sample format: {sample_format!r}"
        raise AudioError(msg)
    path = Path(path)
    data = recording.samples
    if data.shape[1] == 1:
        data = data[:, 0]
    wavfile.write(path, recording.sample_rate, encode(data))
    return path


def dbfs(amplitude: float) -> float:
    """Convert a linear amplitude (full scale 1.0) to decibels re full scale.

    Zero maps to ``-inf``.
    """
    if amplitude <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(amplitude))
