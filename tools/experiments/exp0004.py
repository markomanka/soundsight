# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""EXP-0004: which higher-order edge diffraction closes the gap? (protocol: docs/experiments/).

This script fixes the references and metrics before any candidate exists. It computes the
wave-solver references for workload W2, checks their validity, measures the baseline
(engine increment 1) on them, and provides the functions that will judge each candidate
unchanged.

Usage, from the repository root:
    uv run python tools/experiments/exp0004.py            # compute and store references
    uv run python tools/experiments/exp0004.py --check    # recompute and compare
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tomllib
from pathlib import Path
from typing import Any

import numpy as np

from soundsight.acoustics import canonical as cn
from soundsight.acoustics.reference import fdtd
from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND

ROOT = Path(__file__).resolve().parents[2]
# Run as a script (python tools/experiments/exp0004.py), Python puts only this folder on
# the import path; the repository root is needed for the sibling experiment module.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.experiments import exp0003  # noqa: E402

RESULTS = ROOT / "docs" / "experiments" / "EXP-0004-references.json"
CANDIDATE_RESULTS = ROOT / "docs" / "experiments" / "EXP-0004-candidates.json"
_BUDGETS = tomllib.loads((ROOT / "docs" / "quality" / "budgets.toml").read_text(encoding="utf-8"))
_THRESHOLDS = _BUDGETS["experiments"]["exp0004"]
BAND_LEVEL_DB: float = _THRESHOLDS["band_level_db"]
SPECTRUM_ERROR: float = _THRESHOLDS["spectrum_error"]
OVERLAP_AGREEMENT_DB: float = _THRESHOLDS["reference_overlap_db"]
COMPACT_LIMIT_AGREEMENT: float = _THRESHOLDS["reference_compact_limit"]
REPRODUCIBILITY_DB: float = _BUDGETS["experiments"]["reproducibility_db"]

# ---- Workload W2, fixed by the protocol (pre-registered 2026-11-17) -------------------
RADIUS_M = 0.1
DISTANCE_M = 0.77
CELLS_PER_RADIUS = 16
#: (ka at the peak of the excitation, extra recorded path in radii) for the two runs.
RUNS = {"low": (0.6, 8), "high": (2.0, 8)}
#: Bands of ka (lower inclusive, upper exclusive) and the run that supplies each.
BANDS: tuple[tuple[float, float, str], ...] = (
    (0.25, 0.5, "low"),
    (0.5, 1.0, "low"),
    (1.0, 2.0, "high"),
    (2.0, 4.0, "high"),
)
#: Both runs cover this band; they must agree there (a check of the reference itself).
OVERLAP_BAND = (1.0, 1.3)
#: Fixed frequencies per band, spaced evenly in ka. Levels are never averaged over FFT
#: bins: bins move with the recording length, which biases averages on steep spectra.
POINTS_PER_BAND = 12


def band_ka(lo: float, hi: float) -> np.ndarray:
    """Return the fixed ka values of a band (lower inclusive, upper exclusive)."""
    return np.linspace(lo, hi, POINTS_PER_BAND, endpoint=False)


def _hz(ka: np.ndarray) -> np.ndarray:
    return ka * SPEED_OF_SOUND / (2.0 * math.pi * RADIUS_M)


def reference_run(name: str) -> fdtd.EchoRatio:
    """Run the wave solver for one excitation, at the fixed frequencies it supplies."""
    ka_peak, tail_radii = RUNS[name]
    ka = np.concatenate(
        [band_ka(lo, hi) for lo, hi, run in BANDS if run == name] + [band_ka(*OVERLAP_BAND)]
    )
    h = RADIUS_M / (CELLS_PER_RADIUS + fdtd.DISK_EDGE_OFFSET_CELLS)
    return fdtd.monostatic_echo_ratio(
        "disk",
        distance_cells=round(DISTANCE_M / h + 0.5),
        radius_cells=CELLS_PER_RADIUS,
        h=h,
        peak_frequency_hz=ka_peak * SPEED_OF_SOUND / (2.0 * math.pi * RADIUS_M),
        tail_cells=tail_radii * CELLS_PER_RADIUS,
        frequencies_hz=_hz(np.sort(ka)),
    )


def _select(run: fdtd.EchoRatio, ka: np.ndarray) -> np.ndarray:
    """Return indices of the run's frequencies that equal the given ka values."""
    run_ka = 2.0 * math.pi * run.frequency_hz * run.radius / SPEED_OF_SOUND
    idx = np.array([int(np.argmin(np.abs(run_ka - k))) for k in ka])
    if not np.allclose(run_ka[idx], ka, rtol=1e-9):
        msg = "requested ka values are missing from the reference run"
        raise RuntimeError(msg)
    return idx


def band_levels(model: cn.EchoModel, runs: dict[str, fdtd.EchoRatio]) -> list[dict[str, Any]]:
    """Echo level and spectrum error of ``model`` against the reference, per band of W2."""
    out = []
    for lo, hi, name in BANDS:
        run = runs[name]
        idx = _select(run, band_ka(lo, hi))
        modelled = model.echo_ratio(cn.Disk(run.radius, run.distance), run.frequency_hz[idx])
        reference = run.ratio[idx]
        ref_db, model_db = cn.band_level_db(reference), cn.band_level_db(modelled)
        error = float(np.mean(np.abs(reference - modelled) / np.abs(reference)))
        out.append(
            {
                "ka_band": [lo, hi],
                "n_frequencies": int(idx.size),
                "reference_level_db": round(ref_db, 4),
                "model_level_db": round(model_db, 4),
                "level_error_db": round(model_db - ref_db, 4),
                "level_pass": abs(model_db - ref_db) <= BAND_LEVEL_DB,
                "spectrum_error": round(error, 4),
                "spectrum_pass": error <= SPECTRUM_ERROR,
            }
        )
    return out


def overlap_check(runs: dict[str, fdtd.EchoRatio]) -> dict[str, Any]:
    """Compare the two reference runs at the same frequencies, where both are excited."""
    ka = band_ka(*OVERLAP_BAND)
    low = runs["low"].ratio[_select(runs["low"], ka)]
    high = runs["high"].ratio[_select(runs["high"], ka)]
    difference = cn.band_level_db(low) - cn.band_level_db(high)
    return {
        "ka_band": list(OVERLAP_BAND),
        "low_run_db": round(cn.band_level_db(low), 4),
        "high_run_db": round(cn.band_level_db(high), 4),
        "difference_db": round(difference, 4),
        "max_pointwise_difference": round(float(np.max(np.abs(low - high) / np.abs(high))), 5),
        "pass": abs(difference) <= OVERLAP_AGREEMENT_DB,
    }


def compact_limit_check(runs: dict[str, fdtd.EchoRatio]) -> dict[str, Any]:
    """At the lowest frequency the reference must approach the exact small-disk limit."""
    run = runs["low"]
    idx = _select(run, band_ka(*BANDS[0][:2])[:1])
    exact = cn.CompactModel().echo_ratio(cn.Disk(run.radius, run.distance), run.frequency_hz[idx])
    error = float(np.abs(run.ratio[idx][0] - exact[0]) / np.abs(exact[0]))
    return {
        "ka": float(BANDS[0][0]),
        "relative_difference": round(error, 5),
        "pass": error <= COMPACT_LIMIT_AGREEMENT,
    }


def compute() -> dict[str, Any]:
    """Compute references, their validity checks and the baseline."""
    runs = {name: reference_run(name) for name in RUNS}
    baseline = cn.PlateEngineModel()
    return {
        "experiment": "EXP-0004",
        "workload": "W2",
        "geometry": {"radius_m": RADIUS_M, "distance_m": runs["low"].distance},
        "reference_overlap": overlap_check(runs),
        "reference_compact_limit": compact_limit_check(runs),
        "baseline": {"model": baseline.name, "bands": band_levels(baseline, runs)},
    }


# ---- Candidate evaluation: the same metrics as the baseline, unchanged ---------------
COST_TARGET = cn.Disk(radius=0.127, distance=0.33)
COST_FREQUENCIES_HZ = np.linspace(2000.0, 4000.0, 20)
COST_SAMPLE_RATE = 48_000
COST_SAMPLES = 4096


def _candidates() -> dict[str, Any]:
    """Each candidate: its model, and how it renders the W4(b) impulse response."""
    from soundsight.acoustics.candidates import all_orders, second_order  # noqa: PLC0415

    def c1_ir(plate: Any, budget_s: float) -> None:  # noqa: ARG001 - C1 is far inside it
        echo = second_order.plate_echo_second_order(plate, (0, 0, 0), f_max=COST_SAMPLE_RATE / 2)
        second_order.render_dense(echo, COST_SAMPLE_RATE, COST_SAMPLES)

    def c2_ir(plate: Any, budget_s: float) -> None:
        all_orders.impulse_response(
            plate, (0, 0, 0), None, COST_SAMPLE_RATE, COST_SAMPLES, budget_s=budget_s
        )

    return {
        "c1": (second_order.SecondOrderPlateModel, c1_ir),
        "c2": (all_orders.AllOrdersPlateModel, c2_ir),
    }


def w1(model: cn.EchoModel) -> dict[str, Any]:
    """W1: EXP-0003 with the candidate, against EXP-0003's stored (CI-checked) references."""
    stored = json.loads(exp0003.RESULTS.read_text(encoding="utf-8"))
    cases = []
    for c in stored["cases"]:
        target = cn.Disk(c["acoustic_radius_m"], c["acoustic_distance_m"])
        level = cn.band_level_db(model.echo_ratio(target, exp0003.BAND_FREQUENCIES_HZ))
        cases.append(
            {
                k: c[k]
                for k in ("diameter_cm", "distance_cm", "reference_level_db", "acoustic_radius_m")
            }
            | {"engine_level_db": round(level, 4)}
        )
    result = exp0003.evaluate(cases)
    s = result["summary"]
    result["accepted"] = s["level_pass"] == s["n_cases"] and s["cue_pass"] == s["n_cues"]
    return result


def w4(name: str, *, runs: int = 3) -> dict[str, Any]:
    """W4: median of ``runs`` timings for the pre-registered cost workloads.

    A run of the impulse response that exceeds its budget is stopped there: the budget
    is pass or fail, and continuing cannot change the verdict. Such runs count as over
    budget in the median.
    """
    import time  # noqa: PLC0415

    from soundsight.acoustics.candidates.all_orders import BudgetExceededError  # noqa: PLC0415
    from soundsight.acoustics.engine import Plate  # noqa: PLC0415

    model_cls, render_ir = _candidates()[name]
    model = model_cls()
    budget_fr = float(_THRESHOLDS["cost_frequency_response_s"])
    budget_ir = float(_THRESHOLDS["cost_impulse_response_s"])
    centre = (0.0, 0.0, COST_TARGET.distance)
    plate = Plate.regular(COST_TARGET.radius, model.n_sides, centre=centre)
    fr_times, ir_times, stopped = [], [], []
    for _ in range(runs):
        t = time.perf_counter()
        model.echo_ratio(COST_TARGET, COST_FREQUENCIES_HZ)
        fr_times.append(time.perf_counter() - t)
        t = time.perf_counter()
        try:
            render_ir(plate, budget_ir)
        except BudgetExceededError as exc:
            stopped.append(f"{exc.done} of {exc.total} frequencies")
            ir_times.append(float("inf"))
            continue
        ir_times.append(time.perf_counter() - t)
    fr, ir = float(np.median(fr_times)), float(np.median(ir_times))
    return {
        "runs": runs,
        "frequency_response_s": round(fr, 2),
        "impulse_response_s": round(ir, 2) if math.isfinite(ir) else None,
        "impulse_response_stopped_at_budget": stopped,
        "budget_frequency_response_s": budget_fr,
        "budget_impulse_response_s": budget_ir,
        "accepted": fr <= budget_fr and ir <= budget_ir,
    }


def evaluate_candidate(name: str, parts: tuple[str, ...] = ("W1", "W2", "W4")) -> dict[str, Any]:
    """Run the requested workloads for a candidate (W3 is its test suite, run by CI)."""
    model = _candidates()[name][0]()
    out: dict[str, Any] = {"candidate": name, "model": model.name}
    if "W1" in parts:
        out["W1"] = w1(model)
    if "W2" in parts:
        runs = {run: reference_run(run) for run in RUNS}
        bands = band_levels(model, runs)
        out["W2"] = {
            "bands": bands,
            "accepted": all(b["level_pass"] and b["spectrum_pass"] for b in bands),
        }
    if "W4" in parts:
        out["W4"] = w4(name)
    return out


def compare(fresh: dict[str, Any], stored: dict[str, Any]) -> list[str]:
    """Differences between a fresh computation and the stored file."""
    problems = []
    for new, old in zip(fresh["baseline"]["bands"], stored["baseline"]["bands"], strict=True):
        for key in ("reference_level_db", "model_level_db"):
            if abs(new[key] - old[key]) > REPRODUCIBILITY_DB:
                problems.append(f"ka {new['ka_band']}: {key} {new[key]} differs from {old[key]}")
    if not fresh["reference_overlap"]["pass"]:
        problems.append("the two reference runs disagree in their overlap band")
    if not fresh["reference_compact_limit"]["pass"]:
        problems.append("the reference does not approach the exact small-disk limit")
    return problems


def main(argv: list[str] | None = None) -> int:
    """Compute EXP-0004 references; write them or check them."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare with the stored file")
    parser.add_argument("--candidate", help="evaluate a candidate (c1, c2) instead")
    parser.add_argument("--parts", default="W1,W2,W4", help="workloads to run, e.g. W1,W2")
    args = parser.parse_args(argv)
    if args.candidate:
        parts = tuple(p.strip() for p in args.parts.split(","))
        return _run_candidate(args.candidate, check=args.check, parts=parts)
    fresh = compute()
    o, k = fresh["reference_overlap"], fresh["reference_compact_limit"]
    print(f"reference self-check, ka {o['ka_band']}: runs differ by {o['difference_db']:+.3f} dB")
    print(
        f"reference against exact small-disk limit at ka {k['ka']}: {k['relative_difference']:.4f}"
    )
    for b in fresh["baseline"]["bands"]:
        print(
            f"ka {b['ka_band'][0]}-{b['ka_band'][1]}: reference {b['reference_level_db']:+.2f} dB, "
            f"baseline {b['model_level_db']:+.2f} dB (error {b['level_error_db']:+.2f} dB, "
            f"spectrum {100 * b['spectrum_error']:.0f}%)"
        )
    if args.check:
        problems = compare(fresh, json.loads(RESULTS.read_text(encoding="utf-8")))
        for p in problems:
            print(f"EXP-0004: {p}", file=sys.stderr)
        return 1 if problems else 0
    if not (o["pass"] and k["pass"]):
        print("EXP-0004: references failed a validity check; not written", file=sys.stderr)
        return 1
    RESULTS.write_text(json.dumps(fresh, indent=2) + "\n", encoding="utf-8")
    print(f"written: {RESULTS.relative_to(ROOT)}")
    return 0


def _run_candidate(name: str, *, check: bool, parts: tuple[str, ...]) -> int:
    result = evaluate_candidate(name, parts)
    if "W1" in result:
        s = result["W1"]["summary"]
        print(f"W1: levels {s['level_pass']}/18, cues {s['cue_pass']}/15")
    for b in result.get("W2", {}).get("bands", []):
        print(
            f"W2 ka {b['ka_band']}: level error {b['level_error_db']:+.2f} dB, spectrum "
            f"{100 * b['spectrum_error']:.0f}%"
        )
    if "W4" in result:
        w = result["W4"]
        ir = w["impulse_response_s"]
        ir_text = (
            f"{ir} s"
            if ir is not None
            else (
                f"over the {w['budget_impulse_response_s']} s budget "
                f"(stopped at {', '.join(w['impulse_response_stopped_at_budget'])})"
            )
        )
        # A notice annotation makes the cost measured on the CI runner visible on the run page.
        print(
            f"::notice title=EXP-0004 W4 cost ({name})::frequency response "
            f"{w['frequency_response_s']} s, impulse response {ir_text}"
        )
    stored_all = (
        json.loads(CANDIDATE_RESULTS.read_text(encoding="utf-8"))
        if CANDIDATE_RESULTS.is_file()
        else {}
    )
    if check:
        stored = stored_all[name]
        problems = []
        if "W2" in result:
            for new, old in zip(result["W2"]["bands"], stored["W2"]["bands"], strict=True):
                if abs(new["model_level_db"] - old["model_level_db"]) > REPRODUCIBILITY_DB:
                    problems.append(f"W2 ka {new['ka_band']}: level differs from stored")
        if "W1" in result and result["W1"]["summary"] != stored["W1"]["summary"]:
            problems.append("W1 verdicts differ from stored")
        if "W4" in result and result["W4"]["accepted"] != stored["W4"]["accepted"]:
            problems.append("W4 verdict differs from stored")
        for p in problems:
            print(f"EXP-0004: {p}", file=sys.stderr)
        return 1 if problems else 0
    merged = stored_all.get(name, {}) | result
    stored_all[name] = merged
    CANDIDATE_RESULTS.write_text(json.dumps(stored_all, indent=2) + "\n", encoding="utf-8")
    print(f"written: {CANDIDATE_RESULTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
