# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the repository tools that CI relies on."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tools import check_dependency_licenses as licences
from tools import check_docs as docs
from tools import check_repo_hygiene as hygiene
from tools import fetch_legacy_click as fetch
from tools.experiments import exp0003, exp0004


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


# ---------------------------------------------------------------- EXP-0003 runner


def test_exp0003_reference_grid_meets_both_resolution_rules() -> None:
    for diameter in exp0003.DIAMETERS_CM:
        radius = diameter / 200
        cells, h = exp0003.reference_grid(radius)
        assert cells >= exp0003.MIN_CELLS_PER_RADIUS
        assert (343.0 / 4000.0) / h >= exp0003.MIN_CELLS_PER_WAVELENGTH_AT_4KHZ


def test_exp0003_thresholds_come_from_the_budgets_file() -> None:
    assert exp0003.LEVEL_THRESHOLD_DB == 1.0
    assert exp0003.CUE_THRESHOLD_DB == 1.5


def _case(diameter: float, distance: float, ref: float, eng: float) -> dict[str, object]:
    return {
        "diameter_cm": diameter,
        "distance_cm": distance,
        "reference_level_db": ref,
        "engine_level_db": eng,
    }


def test_exp0003_decision_rule_per_trial() -> None:
    cases = []
    for distance in exp0003.DISTANCES_CM:
        for diameter in exp0003.DIAMETERS_CM:
            error = 2.0 if diameter == 5.1 else 0.1  # only the smallest disc is wrong
            cases.append(_case(diameter, distance, -diameter, -diameter + error))
    result = exp0003.evaluate(cases)
    s = result["summary"]
    assert (s["level_pass"], s["n_cases"]) == (15, 18)
    assert (s["cue_pass"], s["n_cues"]) == (12, 15)
    assert s["trials_using_engine"] == 12  # reference disc stays usable: per-trial reading


def _full_grid() -> list[dict[str, object]]:
    return [
        _case(diameter, distance, -diameter, -diameter + 0.1)
        for distance in exp0003.DISTANCES_CM
        for diameter in exp0003.DIAMETERS_CM
    ]


def test_exp0003_compare_detects_drift_and_verdict_changes() -> None:
    stored = exp0003.evaluate(_full_grid())
    assert exp0003.compare(exp0003.evaluate(_full_grid()), stored) == []
    drifted = _full_grid()
    drifted[2]["engine_level_db"] = -13.5 - 1.6  # moves 1.7 dB and flips the verdict
    problems = exp0003.compare(exp0003.evaluate(drifted), stored)
    assert any("differs from stored" in p for p in problems)
    assert any("verdict changed" in p for p in problems)
    missing = exp0003.evaluate(_full_grid())
    missing["cases"] = missing["cases"][:-1]
    assert any("is new" in p for p in exp0003.compare(stored, missing))


def test_exp0003_stored_results_are_complete_and_consistent() -> None:
    stored = json.loads(exp0003.RESULTS.read_text(encoding="utf-8"))
    assert stored["summary"]["n_cases"] == 18
    recomputed = exp0003.evaluate(
        [
            {
                k: c[k]
                for k in (
                    "diameter_cm",
                    "distance_cm",
                    "reference_level_db",
                    "engine_level_db",
                    "acoustic_radius_m",
                )
            }
            for c in stored["cases"]
        ]
    )
    assert recomputed["summary"] == stored["summary"]


# ---------------------------------------------------------------- EXP-0004 protocol
def test_exp0004_bands_are_fixed_and_cover_the_gap() -> None:
    bands = [(lo, hi) for lo, hi, _ in exp0004.BANDS]
    assert bands == [(0.25, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 4.0)]
    ka = exp0004.band_ka(1.0, 2.0)
    assert ka.size == exp0004.POINTS_PER_BAND
    assert ka[0] == 1.0
    assert ka[-1] < 2.0
    assert exp0004.BAND_LEVEL_DB == 1.0
    assert exp0004.SPECTRUM_ERROR == 0.10


def test_exp0004_stored_references_are_valid_and_baseline_fails() -> None:
    stored = json.loads(exp0004.RESULTS.read_text(encoding="utf-8"))
    assert stored["reference_overlap"]["pass"]
    assert stored["reference_compact_limit"]["pass"]
    bands = stored["baseline"]["bands"]
    assert len(bands) == 4
    assert all(b["n_frequencies"] == exp0004.POINTS_PER_BAND for b in bands)
    # The baseline (first-order engine) is what this experiment must improve on.
    assert not all(b["level_pass"] and b["spectrum_pass"] for b in bands)


def test_exp0004_compare_detects_drift() -> None:
    stored = json.loads(exp0004.RESULTS.read_text(encoding="utf-8"))
    assert exp0004.compare(stored, stored) == []
    drifted = json.loads(json.dumps(stored))
    drifted["baseline"]["bands"][0]["reference_level_db"] += 0.5
    drifted["reference_overlap"]["pass"] = False
    problems = exp0004.compare(drifted, stored)
    assert any("differs" in p for p in problems)
    assert any("disagree" in p for p in problems)


def test_exp0004_candidate_results_are_complete() -> None:
    stored = json.loads(exp0004.CANDIDATE_RESULTS.read_text(encoding="utf-8"))["c1"]
    assert stored["W1"]["summary"]["n_cases"] == 18
    assert len(stored["W2"]["bands"]) == 4
    assert {"frequency_response_s", "impulse_response_s", "accepted"} <= stored["W4"].keys()
    # Recorded verdicts follow from the recorded numbers.
    assert stored["W1"]["accepted"] == (
        stored["W1"]["summary"]["level_pass"] == 18 and stored["W1"]["summary"]["cue_pass"] == 15
    )
    assert stored["W2"]["accepted"] == all(
        b["level_pass"] and b["spectrum_pass"] for b in stored["W2"]["bands"]
    )


@pytest.mark.parametrize("script", ["exp0003.py", "exp0004.py"])
def test_experiment_scripts_run_the_way_ci_runs_them(script: str) -> None:
    """CI runs the scripts as plain files, with only their own folder on the import path
    (a missing import there once failed CI while passing locally)."""
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "experiments" / script), "--help"],
        capture_output=True,
        text=True,
        check=False,
        cwd=root,
        env={k: v for k, v in __import__("os").environ.items() if k != "PYTHONPATH"},
    )
    assert result.returncode == 0, result.stderr


def test_exp0005_stored_results_are_complete_and_consistent() -> None:
    stored = json.loads(
        (
            Path(__file__).resolve().parents[1] / "docs" / "experiments" / "EXP-0005-results.json"
        ).read_text(encoding="utf-8")
    )
    assert len(stored["combinations"]) == 36
    for name in ("R1", "R2"):
        s = stored["summary"][name]
        assert s["m1_pass"] == sum(c[name]["m1_pass"] for c in stored["combinations"])
        assert s["m2_pass"] == sum(c[name]["m2_pass"] for c in stored["combinations"])
        assert s["accepted"] == (s["m1_pass"] == s["m2_pass"] == 36 and s["M3"]["m3_pass"])
