# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the repository tools that CI relies on."""

from __future__ import annotations

from pathlib import Path

import pytest
from tools import check_dependency_licenses as licences
from tools import check_docs as docs
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


# ---------------------------------------------------------------- dependency licences
POLICY = licences.Policy(
    runtime=frozenset({"MIT", "BSD-3-Clause", "Apache-2.0"}),
    development=frozenset({"MIT", "BSD-3-Clause", "Apache-2.0", "GPL-3.0-or-later"}),
    overrides={"opaque": "BSD-3-Clause"},
)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("MIT", True),
        ("BSD-3-Clause AND MIT", True),
        ("BSD-3-Clause AND Proprietary", False),
        ("Apache-2.0 OR GPL-2.0-only", True),  # a choice: we may take the allowed side
        ("GPL-2.0-only OR LGPL-2.1-only", False),
        ("(MIT OR GPL-2.0-only) AND BSD-3-Clause", False),  # bracketed: be conservative
        ("", False),
    ],
)
def test_licence_expression_rules(expression: str, expected: bool) -> None:
    assert licences.is_allowed(expression, POLICY.runtime) is expected


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        ({"License-Expression": "MIT"}, "MIT"),
        ({"License": "Apache 2.0"}, "Apache-2.0"),
        ({"License": "BSD-3-Clause AND MIT"}, "BSD-3-Clause AND MIT"),
        ({"License": "Copyright (c) 2001 Somebody, Inc. All rights reserved."}, None),
        ({"License": "Free for research use only"}, None),
        ({"classifiers": ["License :: OSI Approved :: MIT License"]}, "MIT"),
        ({"classifiers": ["License :: OSI Approved :: BSD License"]}, None),  # ambiguous
        ({}, None),
    ],
)
def test_declared_licence_detection(meta: dict[str, object], expected: str | None) -> None:
    assert licences.declared_license("pkg", meta, {}) == expected


def test_override_wins_over_metadata() -> None:
    assert licences.declared_license("opaque", {"License": "whatever"}, POLICY.overrides) == (
        "BSD-3-Clause"
    )


def test_audit_separates_runtime_from_development() -> None:
    packages: dict[str, dict[str, object]] = {
        "soundsight": {},
        "numlib": {"License-Expression": "BSD-3-Clause"},
        "deep": {"License-Expression": "GPL-3.0-or-later"},  # reached at run time: not allowed
        "linter": {"License-Expression": "GPL-3.0-or-later"},  # a tool: allowed
        "mystery": {"License": "see the website"},
        "closed": {"License-Expression": "LicenseRef-Proprietary"},
    }
    requirements = {
        "soundsight": ["numlib>=1", "optional-thing; extra == 'gui'"],
        "numlib": ["deep"],
    }
    problems = licences.audit(packages, requirements, POLICY)
    assert problems == [
        "closed (development): licence 'LicenseRef-Proprietary' is not on the "
        "development allowlist",
        "deep (runtime): licence 'GPL-3.0-or-later' is not on the runtime allowlist",
        "mystery (development): licence cannot be determined; review it and add an override",
    ]


def test_a_closed_engine_like_the_2016_one_would_be_rejected() -> None:
    packages: dict[str, dict[str, object]] = {
        "soundsight": {},
        "gsound": {"License": "Educational, research and non-profit use only"},
    }
    [problem] = licences.audit(packages, {"soundsight": ["gsound"]}, POLICY)
    assert problem.startswith("gsound (runtime): licence cannot be determined")


def test_policy_file_is_valid() -> None:
    policy = licences.load_policy()
    assert "Apache-2.0" in policy.runtime
    assert policy.runtime < policy.development
    assert set(policy.overrides) >= {"scipy", "colorama"}


@pytest.mark.locked_env
def test_every_installed_dependency_has_an_allowed_licence() -> None:
    """Runs on each operating system of the CI matrix, so platform-only packages count."""
    packages, requirements = licences.installed()
    assert licences.audit(packages, requirements, licences.load_policy()) == []
    assert {"numpy", "scipy"} <= licences.runtime_closure(requirements)


def test_policy_overrides_must_record_a_review(tmp_path: Path) -> None:
    bad = tmp_path / "licenses.toml"
    bad.write_text(
        '[runtime]\nallowed = ["MIT"]\n[development]\nallowed = []\n'
        '[overrides.x]\nlicense = "MIT"\n'
    )
    with pytest.raises(ValueError, match="reviewed"):
        licences.load_policy(bad)


# ---------------------------------------------------------------- evidence citations
REGISTER = """
| ID | Citation | Used by | Kind | Checked |
| --- | --- | --- | --- | --- |
| A1 | Someone (2020). | decision 2 | Study | PubMed |
| B2 | Another (2021). | EXP-0001 | Review | Unchecked |
"""


def _repo(tmp_path: Path, decision: str, register: str = REGISTER) -> Path:
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "docs" / "experiments").mkdir()
    (tmp_path / "docs" / "decisions").mkdir()
    (tmp_path / "docs" / "research" / "literature.md").write_text(register)
    (tmp_path / "docs" / "experiments" / "EXP-0001-something.md").write_text("x")
    (tmp_path / "docs" / "decisions" / "0001-x.md").write_text(decision)
    return tmp_path


def test_decision_citing_existing_evidence_passes(tmp_path: Path) -> None:
    root = _repo(tmp_path, "# D\n\nLiterature: A1, B2.\nExperiments: EXP-0001.\n")
    assert docs.check_repository(root) == []


def test_decision_may_say_none_with_a_reason(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        "Literature: none (a licensing decision, not a scientific one).\n"
        "Experiments: none (decided from the licence text).\n",
    )
    assert docs.check_repository(root) == []


@pytest.mark.parametrize(
    ("decision", "fragment"),
    [
        ("Experiments: EXP-0001.\n", "no 'Literature:' line"),
        ("Literature: A1.\n", "no 'Experiments:' line"),
        ("Literature: none.\nExperiments: EXP-0001.\n", "cites nothing"),
        ("Literature: Z9.\nExperiments: EXP-0001.\n", "literature Z9 is not in"),
        ("Literature: A1.\nExperiments: EXP-0042.\n", "experiments EXP-0042 is not in"),
    ],
)
def test_decision_problems_are_reported(tmp_path: Path, decision: str, fragment: str) -> None:
    problems = docs.check_repository(_repo(tmp_path, decision))
    assert any(fragment in p for p in problems), problems


def test_register_problems_are_reported(tmp_path: Path) -> None:
    register = (
        REGISTER
        + "| A1 | Duplicate. | something | Study | PubMed |\n| C3 | Orphan. | | Study | PubMed |\n"
    )
    problems = docs.check_repository(
        _repo(tmp_path, "Literature: A1.\nExperiments: EXP-0001.\n", register)
    )
    assert "literature register: identifier A1 appears twice" in problems
    assert "literature register: C3 names no consumer" in problems


def test_missing_register_and_missing_decisions(tmp_path: Path) -> None:
    assert docs.check_repository(tmp_path) == ["docs/research/literature.md is missing"]
    root = _repo(tmp_path, "x")
    (root / "docs" / "decisions" / "0001-x.md").unlink()
    assert "no decision records found in docs/decisions/" in docs.check_repository(root)


def test_this_repository_cites_its_evidence() -> None:
    assert docs.check_repository() == []
