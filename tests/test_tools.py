# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the repository tools that CI relies on."""

from __future__ import annotations

from pathlib import Path

import pytest
from tools import check_repo_hygiene as hygiene
from tools import fetch_legacy_click as fetch


def test_hygiene_accepts_source(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    assert hygiene.violations([Path("a.py")], root=tmp_path) == []


@pytest.mark.parametrize("name", ["GSound.lib", "SOUNDSIGHT.exe", "x.pdb", "mod.SO"])
def test_hygiene_rejects_binaries(tmp_path: Path, name: str) -> None:
    (tmp_path / name).write_bytes(b"\0")
    [problem] = hygiene.violations([Path(name)], root=tmp_path)
    assert "not allowed" in problem


def test_hygiene_rejects_generated_dirs(tmp_path: Path) -> None:
    (tmp_path / "Debug").mkdir()
    (tmp_path / "Debug" / "log.txt").write_text("x")
    [problem] = hygiene.violations([Path("Debug/log.txt")], root=tmp_path)
    assert "generated" in problem


def test_hygiene_rejects_large_files(tmp_path: Path) -> None:
    (tmp_path / "big.wav").write_bytes(b"\0" * 2048)
    [problem] = hygiene.violations([Path("big.wav")], root=tmp_path, max_bytes=1024)
    assert "exceeds" in problem


def test_hygiene_lists_files_without_git(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("")
    (tmp_path / ".git").mkdir()  # an empty .git directory is not a repository
    (tmp_path / ".git" / "HEAD").write_text("")
    files = hygiene.tracked_files(tmp_path)
    assert Path("src/a.py") in files
    assert not any(".git" in p.parts for p in files)


def test_this_repository_is_clean() -> None:
    assert hygiene.violations(hygiene.tracked_files()) == []


def test_checksum_verification(tmp_path: Path) -> None:
    f = tmp_path / "x.bin"
    f.write_bytes(b"abc")
    digest = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert fetch.sha256_of(f) == digest
    assert fetch.is_valid(f, digest)
    assert not fetch.is_valid(f, "0" * 64)
    assert not fetch.is_valid(tmp_path / "missing", digest)


def test_fetch_skips_verified_copy(tmp_path: Path) -> None:
    f = tmp_path / "x.bin"
    f.write_bytes(b"abc")
    digest = fetch.sha256_of(f)
    assert fetch.fetch(dest=f, url="https://invalid.example/never-used", expected=digest) == f


def test_fetch_pins_commit_and_digest() -> None:
    assert fetch.COMMIT in fetch.URL
    assert len(fetch.COMMIT) == 40
    assert len(fetch.SHA256) == 64
