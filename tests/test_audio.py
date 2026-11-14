# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for soundsight.audio."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from soundsight.audio import AudioError, Recording, dbfs, from_array, read_wav, write_wav


def test_mono_array_becomes_one_channel() -> None:
    rec = from_array([0.0, 0.5, -0.5], 8000)
    assert rec.samples.shape == (3, 1)
    assert rec.n_frames == 3
    assert rec.n_channels == 1
    assert rec.duration_s == pytest.approx(3 / 8000)


def test_samples_are_read_only_copies() -> None:
    source = np.zeros((10, 2))
    rec = Recording(source, 44100)
    source[0, 0] = 1.0
    assert rec.samples[0, 0] == 0.0
    with pytest.raises(ValueError, match="read-only"):
        rec.samples[0, 0] = 1.0


@pytest.mark.parametrize(
    ("samples", "message"),
    [
        (np.zeros(0), "empty"),
        (np.zeros((0, 2)), "empty"),
        (np.zeros((2, 2, 2)), "dimensions"),
        (np.array([0.0, np.nan]), "NaN"),
        (np.array([0.0, np.inf]), "NaN"),
    ],
)
def test_invalid_samples_rejected(samples: np.ndarray, message: str) -> None:
    with pytest.raises(AudioError, match=message):
        Recording(samples, 44100)


@pytest.mark.parametrize("rate", [0, -1])
def test_invalid_sample_rate_rejected(rate: int) -> None:
    with pytest.raises(AudioError, match="positive"):
        Recording(np.zeros(4), rate)


@pytest.mark.parametrize("rate", [44100.0, True])
def test_non_integer_sample_rate_rejected(rate: object) -> None:
    with pytest.raises(AudioError, match="integer"):
        Recording(np.zeros(4), rate)  # type: ignore[arg-type]


def test_numpy_integer_sample_rate_accepted() -> None:
    rec = Recording(np.zeros(4), np.int64(48000))  # type: ignore[arg-type]
    assert rec.sample_rate == 48000
    assert type(rec.sample_rate) is int


def test_channel_selection() -> None:
    rec = Recording(np.array([[1.0, -1.0], [0.5, 0.0]]), 8000)
    np.testing.assert_allclose(rec.channel("mean"), [0.0, 0.25])
    np.testing.assert_allclose(rec.channel(1), [-1.0, 0.0])
    with pytest.raises(AudioError, match="does not exist"):
        rec.channel(2)


@pytest.mark.parametrize("fmt", ["pcm16", "float32"])
def test_write_read_round_trip(tmp_path: Path, fmt: str) -> None:
    rng = np.random.default_rng(1)
    data = rng.uniform(-0.9, 0.9, size=(1000, 2))
    rec = Recording(data, 48000)
    path = write_wav(tmp_path / "x.wav", rec, sample_format=fmt)  # type: ignore[arg-type]
    back = read_wav(path)
    assert back.sample_rate == 48000
    assert back.samples.shape == (1000, 2)
    tolerance = 1.0 / 2**15 if fmt == "pcm16" else 1e-7
    np.testing.assert_allclose(back.samples, data, atol=tolerance)


def test_write_mono_and_pcm16_clips(tmp_path: Path) -> None:
    rec = from_array([2.0, -2.0, 0.0], 8000)
    back = read_wav(write_wav(tmp_path / "m.wav", rec))
    assert back.n_channels == 1
    assert back.samples[0, 0] == pytest.approx(1.0, abs=1e-4)
    assert back.samples[1, 0] == -1.0


def test_write_unknown_format_rejected(tmp_path: Path) -> None:
    with pytest.raises(AudioError, match="unknown sample format"):
        write_wav(tmp_path / "x.wav", from_array([0.0], 8000), sample_format="mp3")  # type: ignore[arg-type]


def _write_raw_wav(path: Path, sampwidth: int, frames: bytes, channels: int = 1) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(16000)
        w.writeframes(frames)


def test_read_24_bit_pcm(tmp_path: Path) -> None:
    values = [0, 2**22, -(2**22), 2**23 - 1, -(2**23)]
    frames = b"".join(v.to_bytes(3, "little", signed=True) for v in values)
    _write_raw_wav(tmp_path / "x.wav", 3, frames)
    got = read_wav(tmp_path / "x.wav").channel(0)
    np.testing.assert_allclose(got, [0.0, 0.5, -0.5, 1 - 2**-23, -1.0], atol=1e-9)


def test_read_8_bit_pcm(tmp_path: Path) -> None:
    _write_raw_wav(tmp_path / "x.wav", 1, bytes([128, 255, 0]))
    got = read_wav(tmp_path / "x.wav").channel(0)
    np.testing.assert_allclose(got, [0.0, 127 / 128, -1.0])


def test_read_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_wav(tmp_path / "nope.wav")


def test_read_non_wav_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"this is not audio at all")
    with pytest.raises(AudioError, match="cannot read"):
        read_wav(bad)


def test_read_ignores_metadata_chunks(tmp_path: Path) -> None:
    # A WAV with an extra 'LIST' chunk, as written by many recorders.
    path = write_wav(tmp_path / "x.wav", from_array([0.1, -0.1], 8000))
    data = path.read_bytes()
    extra = b"LIST" + (4).to_bytes(4, "little") + b"INFO"
    body = data[12:] + extra
    path.write_bytes(b"RIFF" + (len(body) + 4).to_bytes(4, "little") + b"WAVE" + body)
    assert read_wav(path).n_frames == 2


@pytest.mark.parametrize(
    ("amplitude", "expected"), [(1.0, 0.0), (0.1, -20.0), (0.0, float("-inf"))]
)
def test_dbfs(amplitude: float, expected: float) -> None:
    assert dbfs(amplitude) == pytest.approx(expected)
