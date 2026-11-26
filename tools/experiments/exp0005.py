# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""EXP-0005: rendering exercise trials with the accuracy of increment 2.

Protocol: docs/experiments/EXP-0005-exercise-rendering.md.

The full evaluation solves the all-orders equation thousands of times, so every solved
frequency is cached on disk and the run can be resumed:

    uv run python tools/experiments/exp0005.py run --time-limit 250   # repeat until done
    uv run python tools/experiments/exp0005.py assemble               # metrics, cost, results
    uv run python tools/experiments/exp0005.py check                  # CI: R1 in full, R2 sample

The cache lives in data/exp0005-cache (ignored by git), or where SOUNDSIGHT_EXP0005_CACHE
points.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from soundsight.acoustics import engine as eg  # noqa: E402
from soundsight.acoustics.candidates import all_orders  # noqa: E402
from soundsight.acoustics.candidates.all_orders import BudgetExceededError  # noqa: E402
from soundsight.acoustics.canonical import band_level_db  # noqa: E402
from soundsight.audio import read_wav  # noqa: E402
from soundsight.click.detect import detect_clicks  # noqa: E402
from soundsight.click.synth import synth_click  # noqa: E402
from soundsight.exercise import render_all_orders as r2  # noqa: E402
from soundsight.exercise.render import BAND_FREQUENCIES_HZ, render_disc_trial  # noqa: E402
from tools.experiments import exp0003  # noqa: E402

RESULTS = ROOT / "docs" / "experiments" / "EXP-0005-results.json"
CACHE = Path(os.environ.get("SOUNDSIGHT_EXP0005_CACHE", str(ROOT / "data" / "exp0005-cache")))
_BUDGETS = tomllib.loads((ROOT / "docs" / "quality" / "budgets.toml").read_text(encoding="utf-8"))
WEIGHTED_ERROR_DB: float = _BUDGETS["experiments"]["exp0005"]["weighted_error_db"]
BAND_LEVEL_DB: float = _BUDGETS["experiments"]["exp0005"]["band_level_db"]
COST_TRIAL_S: float = _BUDGETS["experiments"]["exp0005"]["cost_trial_s"]
REPRODUCIBILITY_DB: float = _BUDGETS["experiments"]["reproducibility_db"]

FS = 48_000
GRID_HZ = np.geomspace(250.0, 20_000.0, 200)
CLICKS = ("synthetic", "recorded")
REFERENCE_SIDES = 48


def recorded_click() -> np.ndarray:
    """Return the first click of the 2016 recording (clarification 1 of 2026-11-26)."""
    path = ROOT / "data" / "legacy" / "clickrecord.wav"
    if not path.is_file():
        msg = "fetch the recording first: uv run python tools/fetch_legacy_click.py"
        raise FileNotFoundError(msg)
    rec = read_wav(path)
    x = rec.channel("mean")
    event = detect_clicks(x, rec.sample_rate).events[0]
    lo = max(0, event.start_index - round(0.001 * rec.sample_rate))
    hi = event.end_index + round(0.002 * rec.sample_rate)
    return np.asarray(resample_poly(x[lo:hi], 1, rec.sample_rate // FS), dtype=np.float64)


def click(name: str) -> np.ndarray:
    """One of the two workload clicks, at 48 kHz."""
    return synth_click(FS) if name == "synthetic" else recorded_click()


def _cache_file(name: str) -> Path:
    return CACHE / f"{name}.json"


def _load(name: str) -> dict[float, complex]:
    path = _cache_file(name)
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {float(k): complex(v[0], v[1]) for k, v in raw.items()}


def _save(name: str, cache: dict[float, complex]) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    data = {repr(k): [v.real, v.imag] for k, v in cache.items()}
    _cache_file(name).write_text(json.dumps(data), encoding="utf-8")


def _key(diameter_cm: float, distance_cm: float) -> str:
    return f"{diameter_cm:g}cm_{distance_cm:g}cm"


def reference(diameter_cm: float, distance_cm: float, deadline: float | None) -> np.ndarray:
    """C2 at the 200 grid frequencies followed by the 41 band frequencies."""
    name = f"ref_{_key(diameter_cm, distance_cm)}"
    cache = _load(name)
    plate = eg.Plate.regular(diameter_cm / 200, REFERENCE_SIDES, centre=(0, 0, distance_cm / 100))
    freqs = np.concatenate((GRID_HZ, BAND_FREQUENCIES_HZ))
    try:
        return all_orders.frequency_response(
            plate, (0, 0, 0), None, freqs, cache=cache, deadline=deadline
        )
    finally:
        _save(name, cache)


def candidate_ir(
    name: str, diameter_cm: float, distance_cm: float, clk: str, deadline: float | None
) -> np.ndarray:
    """Return a candidate's impulse response for a unit source."""
    d, dist = diameter_cm / 100, distance_cm / 100
    if name == "R1":
        return r2.first_order_impulse_response(d, dist, FS)
    cache_name = f"r2_{clk}_{_key(diameter_cm, distance_cm)}"
    cache = _load(cache_name)
    try:
        return r2.all_orders_impulse_response(
            d, dist, click(clk), FS, cache=cache, deadline=deadline
        )
    finally:
        _save(cache_name, cache)


def metrics(ref: np.ndarray, ir: np.ndarray, clk: np.ndarray) -> dict[str, Any]:
    """M1 (click-weighted error) and M2 (band level) for one combination."""
    ref_grid, ref_band = ref[: GRID_HZ.size], ref[GRID_HZ.size :]
    weight = np.abs(r2.dtft(clk, FS, GRID_HZ)) ** 2
    h_grid = r2.dtft(ir, FS, GRID_HZ)
    error = float(
        np.sum(weight * np.abs(ref_grid - h_grid) ** 2) / np.sum(weight * np.abs(ref_grid) ** 2)
    )
    error_db = 10.0 * math.log10(error) if error > 0 else -math.inf
    level = band_level_db(r2.dtft(ir, FS, BAND_FREQUENCIES_HZ)) - band_level_db(ref_band)
    return {
        "weighted_error_db": round(error_db, 3),
        "m1_pass": error_db <= WEIGHTED_ERROR_DB,
        "band_level_error_db": round(level, 4),
        "m2_pass": abs(level) <= BAND_LEVEL_DB,
    }


def combinations() -> list[tuple[str, float, float]]:
    """All 36 combinations, cheapest first (synthetic click, small discs, far away)."""
    combos = [
        (c, d, dist) for c in CLICKS for dist in exp0003.DISTANCES_CM for d in exp0003.DIAMETERS_CM
    ]
    return sorted(combos, key=lambda x: (CLICKS.index(x[0]), x[1], -x[2]))


def _combo_file(clk: str, d: float, dist: float) -> Path:
    return CACHE / "combos" / f"{clk}_{_key(d, dist)}.json"


def run(time_limit: float | None) -> int:
    """Compute every combination not yet done; stop at the time limit (resumable)."""
    deadline = None if time_limit is None else time.perf_counter() + time_limit
    for clk, d, dist in combinations():
        out = _combo_file(clk, d, dist)
        if out.is_file():
            continue
        try:
            ref = reference(d, dist, deadline)
            c = click(clk)
            result: dict[str, Any] = {"click": clk, "diameter_cm": d, "distance_cm": dist}
            for name in ("R1", "R2"):
                result[name] = metrics(ref, candidate_ir(name, d, dist, clk, deadline), c)
        except BudgetExceededError:
            print(f"time limit reached during {clk}, {d} cm at {dist} cm; run again to resume")
            return 3
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result), encoding="utf-8")
        e1, e2 = result["R1"]["weighted_error_db"], result["R2"]["weighted_error_db"]
        print(
            f"{clk:9s} {d:5.1f} cm at {dist:3.0f} cm: R1 {e1:+7.1f} dB, R2 {e2:+7.1f} dB",
            flush=True,
        )
    print("all 36 combinations done")
    return 0


def cost(name: str, runs: int = 3) -> dict[str, Any]:
    """M3: median of three renders of the costliest combination, stopped at the budget."""
    c = recorded_click()
    times = []
    for _ in range(runs):
        started = time.perf_counter()
        try:
            if name == "R1":
                render_disc_trial(0.254, 0.33, click_reference_distance_m=1.0, click=c)
            else:
                r2.render_disc_trial_all_orders(
                    0.254,
                    0.33,
                    click_reference_distance_m=1.0,
                    click=c,
                    deadline=started + COST_TRIAL_S,
                )
            times.append(time.perf_counter() - started)
        except BudgetExceededError:
            times.append(math.inf)
    median = float(np.median(times))
    return {
        "runs": runs,
        "median_s": round(median, 2) if math.isfinite(median) else None,
        "stopped_at_budget": sum(not math.isfinite(t) for t in times),
        "m3_pass": median <= COST_TRIAL_S,
    }


def assemble() -> int:
    """Gather the 36 combinations, measure cost, apply the decision rule, write results."""
    combos = []
    for clk, d, dist in combinations():
        path = _combo_file(clk, d, dist)
        if not path.is_file():
            print("not all combinations are done; run first", file=sys.stderr)
            return 1
        combos.append(json.loads(path.read_text(encoding="utf-8")))
    summary: dict[str, Any] = {}
    for name in ("R1", "R2"):
        m1 = sum(c[name]["m1_pass"] for c in combos)
        m2 = sum(c[name]["m2_pass"] for c in combos)
        m3 = cost(name)
        summary[name] = {
            "m1_pass": m1,
            "m2_pass": m2,
            "M3": m3,
            "accepted": m1 == m2 == len(combos) and m3["m3_pass"],
        }
        print(
            f"{name}: M1 {m1}/36, M2 {m2}/36, M3 median {m3['median_s']} s "
            f"({m3['stopped_at_budget']} of 3 runs stopped at the budget)"
        )
    RESULTS.write_text(
        json.dumps({"experiment": "EXP-0005", "combinations": combos, "summary": summary}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"written: {RESULTS.relative_to(ROOT)}")
    return 0


def check() -> int:
    """CI: recompute R1 for all 36 combinations and R2 for a sample; compare with stored."""
    stored = {
        (c["click"], c["diameter_cm"], c["distance_cm"]): c
        for c in json.loads(RESULTS.read_text(encoding="utf-8"))["combinations"]
    }
    problems = []
    sample = {("synthetic", 5.1, 99.0), ("synthetic", 9.0, 66.0), ("recorded", 5.1, 99.0)}
    for clk, d, dist in combinations():
        ref = reference(d, dist, None)
        c = click(clk)
        for name in ("R1", "R2") if (clk, d, dist) in sample else ("R1",):
            new = metrics(ref, candidate_ir(name, d, dist, clk, None), c)
            old = stored[(clk, d, dist)][name]
            if abs(new["band_level_error_db"] - old["band_level_error_db"]) > REPRODUCIBILITY_DB:
                problems.append(f"{name} {clk} {d} cm at {dist} cm: band level differs")
            if new["m1_pass"] != old["m1_pass"] or new["m2_pass"] != old["m2_pass"]:
                problems.append(f"{name} {clk} {d} cm at {dist} cm: verdict differs")
    for p in problems:
        print(f"EXP-0005: {p}", file=sys.stderr)
    print(f"checked R1 on 36 combinations and R2 on {len(sample)}: {len(problems)} differences")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    """Command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["run", "assemble", "check"])
    parser.add_argument("--time-limit", type=float, default=None, help="seconds (run only)")
    args = parser.parse_args(argv)
    if args.action == "run":
        return run(args.time_limit)
    return assemble() if args.action == "assemble" else check()


if __name__ == "__main__":
    sys.exit(main())
