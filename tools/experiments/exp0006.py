# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""EXP-0006: exercise trials from a per-disc echo cache.

Protocol: docs/experiments/EXP-0006-echo-cache.md. Workload, reference and accuracy
metrics are those of EXP-0005, reused from its runner unchanged.

    uv run python tools/experiments/exp0006.py build --time-limit 250   # repeat until done
    uv run python tools/experiments/exp0006.py run                      # 36 combinations
    uv run python tools/experiments/exp0006.py cost                     # M3a and M3b
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from soundsight.acoustics.candidates.all_orders import BudgetExceededError  # noqa: E402
from soundsight.exercise import render_cached as r3  # noqa: E402
from tools.experiments import exp0005  # noqa: E402

RESULTS = ROOT / "docs" / "experiments" / "EXP-0006-results.json"
CACHE = exp0005.CACHE
_BUDGETS = tomllib.loads((ROOT / "docs" / "quality" / "budgets.toml").read_text(encoding="utf-8"))
COST_TRIAL_S: float = _BUDGETS["experiments"]["exp0006"]["cost_trial_s"]
COST_CACHE_S: float = _BUDGETS["experiments"]["exp0006"]["cost_cache_s"]


def _store_name(d: float, dist: float) -> str:
    return f"r3_{exp0005._key(d, dist)}"


def _seconds_file(d: float, dist: float) -> Path:
    return CACHE / f"{_store_name(d, dist)}_seconds.json"


def disc_cache(d: float, dist: float, deadline: float | None) -> r3.DiscEchoCache:
    """Build (or resume building) the cache of one disc; record the compute time spent."""
    store = exp0005._load(_store_name(d, dist))
    spent_file = _seconds_file(d, dist)
    spent = json.loads(spent_file.read_text())["seconds"] if spent_file.is_file() else 0.0
    started = time.perf_counter()
    try:
        return r3.build_cache(d / 100, dist / 100, exp0005.FS, store=store, deadline=deadline)
    finally:
        exp0005._save(_store_name(d, dist), store)
        CACHE.mkdir(parents=True, exist_ok=True)
        spent_file.write_text(json.dumps({"seconds": spent + time.perf_counter() - started}))


def build(time_limit: float | None) -> int:
    """Build every disc's cache, cheapest first; resumable."""
    deadline = None if time_limit is None else time.perf_counter() + time_limit
    discs = sorted(
        {(d, dist) for _, d, dist in exp0005.combinations()}, key=lambda x: (x[0], -x[1])
    )
    for d, dist in discs:
        try:
            disc_cache(d, dist, deadline)
        except BudgetExceededError:
            print(f"time limit reached while building {d} cm at {dist} cm; run again")
            return 3
    print("all 18 disc caches built")
    return 0


def run() -> int:
    """Evaluate the 36 combinations from the caches (M1, M2) and write the results."""
    combos = []
    for clk, d, dist in exp0005.combinations():
        cache = disc_cache(d, dist, None)
        ref = exp0005.reference(d, dist, None)
        result: dict[str, Any] = {"click": clk, "diameter_cm": d, "distance_cm": dist}
        result["R3"] = exp0005.metrics(ref, r3.cached_impulse_response(cache), exp0005.click(clk))
        combos.append(result)
    build_s = {
        f"{d:g}cm_{dist:g}cm": round(json.loads(_seconds_file(d, dist).read_text())["seconds"], 1)
        for _, d, dist in exp0005.combinations()
    }
    m1 = sum(c["R3"]["m1_pass"] for c in combos)
    m2 = sum(c["R3"]["m2_pass"] for c in combos)
    RESULTS.write_text(
        json.dumps(
            {
                "experiment": "EXP-0006",
                "combinations": combos,
                "cache_build_seconds_dev": build_s,
                "summary": {"m1_pass": m1, "m2_pass": m2},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"R3: M1 {m1}/36, M2 {m2}/36; written {RESULTS.relative_to(ROOT)}")
    return 0


def cost() -> int:
    """M3a (trial from cache, median of 3) and M3b (fresh cache of the costliest disc)."""
    click = exp0005.recorded_click()
    started = time.perf_counter()
    try:
        cache = r3.build_cache(0.254, 0.33, exp0005.FS, deadline=started + COST_CACHE_S)
        build_s: float = time.perf_counter() - started
    except BudgetExceededError:
        print(f"::notice title=EXP-0006 M3b cache build::over the {COST_CACHE_S:g} s budget")
        return 0
    times = []
    for _ in range(3):
        t = time.perf_counter()
        r3.render_trial_from_cache(cache, click_reference_distance_m=1.0, click=click)
        times.append(time.perf_counter() - t)
    trial = float(np.median(times))
    print(
        f"::notice title=EXP-0006 cost::cache build {build_s:.0f} s (budget {COST_CACHE_S:g} s), "
        f"trial from cache {trial:.2f} s median (budget {COST_TRIAL_S:g} s)"
    )
    return 0 if math.isfinite(trial) else 1


#: Combinations recomputed from scratch in CI (the full run takes about an hour).
CHECK_SAMPLE = (("synthetic", 5.1, 99.0), ("recorded", 5.1, 99.0), ("recorded", 9.0, 66.0))


def check() -> int:
    """CI: recompute a sample of combinations from scratch and compare with stored results."""
    stored = {
        (c["click"], c["diameter_cm"], c["distance_cm"]): c["R3"]
        for c in json.loads(RESULTS.read_text(encoding="utf-8"))["combinations"]
    }
    problems = []
    for clk, d, dist in CHECK_SAMPLE:
        cache = r3.build_cache(d / 100, dist / 100, exp0005.FS)
        ref = exp0005.reference(d, dist, None)
        new = exp0005.metrics(ref, r3.cached_impulse_response(cache), exp0005.click(clk))
        old = stored[(clk, d, dist)]
        if (
            abs(new["band_level_error_db"] - old["band_level_error_db"])
            > exp0005.REPRODUCIBILITY_DB
        ):
            problems.append(f"{clk} {d} cm at {dist} cm: band level differs")
        if new["m1_pass"] != old["m1_pass"] or new["m2_pass"] != old["m2_pass"]:
            problems.append(f"{clk} {d} cm at {dist} cm: verdict differs")
    for p in problems:
        print(f"EXP-0006: {p}", file=sys.stderr)
    print(f"checked {len(CHECK_SAMPLE)} combinations from scratch: {len(problems)} differences")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    """Command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "run", "cost", "check"])
    parser.add_argument("--time-limit", type=float, default=None, help="seconds (build only)")
    args = parser.parse_args(argv)
    if args.action == "build":
        return build(args.time_limit)
    if args.action == "check":
        return check()
    return run() if args.action == "run" else cost()


if __name__ == "__main__":
    sys.exit(main())
