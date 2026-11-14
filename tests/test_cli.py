# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the command-line interface."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from soundsight import __version__
from soundsight.audio import from_array, write_wav
from soundsight.cli import EXIT_FAILED_CHECKS, EXIT_OK, EXIT_USAGE, main
from soundsight.click.synth import ClickParameters, click_train


@pytest.fixture
def clicks_wav(tmp_path: Path) -> Path:
    path = tmp_path / "clicks.wav"
    assert main(["click", "synth", str(path), "--clicks", "6", "--interval", "0.5"]) == EXIT_OK
    return path


def test_synth_then_analyze(clicks_wav: Path, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()
    assert main(["click", "analyze", str(clicks_wav)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "Clicks found: 6." in out
    assert "Result: 0 failures, 0 warnings." in out


def test_analyze_json(clicks_wav: Path, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()
    assert main(["click", "analyze", str(clicks_wav), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["analysis"]["summary"]["n_clicks"] == 6
    assert report["source"] == "clicks.wav"


def test_analyze_verbose_and_channel(clicks_wav: Path, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()
    assert main(["click", "analyze", str(clicks_wav), "--verbose", "--channel", "0"]) == EXIT_OK
    assert "Click 6 at" in capsys.readouterr().out


def test_strict_exit_code_on_failure(tmp_path: Path) -> None:
    x, _ = click_train(48000, 6, 0.5, ClickParameters(amplitude=1.0), noise_dbfs=-70, seed=0)
    path = write_wav(tmp_path / "hot.wav", from_array(np.clip(1.5 * x, -1, 1), 48000))
    assert main(["click", "analyze", str(path)]) == EXIT_OK
    assert main(["click", "analyze", str(path), "--strict"]) == EXIT_FAILED_CHECKS


def test_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["click", "analyze", str(tmp_path / "nope.wav")]) == EXIT_USAGE
    assert "no such file" in capsys.readouterr().err


def test_bad_synth_parameters(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["click", "synth", str(tmp_path / "x.wav"), "--peak-hz", "30000"])
    assert code == EXIT_USAGE
    assert "Nyquist" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["left", "-1"])
def test_bad_channel_argument(value: str, clicks_wav: Path) -> None:
    with pytest.raises(SystemExit) as info:
        main(["click", "analyze", str(clicks_wav), "--channel", value])
    assert info.value.code == EXIT_USAGE


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_python_dash_m_entry_point(clicks_wav: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "soundsight", "click", "analyze", str(clicks_wav)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == EXIT_OK, result.stderr
    assert "Clicks found: 6." in result.stdout
