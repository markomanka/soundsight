# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""EXP-0003: echoes of the size-discrimination discs (protocol: docs/experiments/).

Computes, for 6 discs x 3 distances, the echo level over the click band with the wave
solver (the pre-registered reference) and with the engine, and applies the
pre-registered thresholds. Results are written as JSON next to the protocol.

Usage, from the repository root:
    uv run python tools/experiments/exp0003.py            # run and write results
    uv run python tools/experiments/exp0003.py --check    # run and compare with the file
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

from soundsight.acoustics import canonical as cn
from soundsight.acoustics.reference import fdtd
from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "experiments" / "EXP-0003-results.json"

# ---- Fixed by the protocol (pre-registered 2026-11-15) -------------------------------
DIAMETERS_CM = (5.1, 9.0, 13.5, 17.5, 22.9, 25.4)
DISTANCES_CM = (33.0, 66.0, 99.0)
REFERENCE_DIAMETER_CM = 25.4
MIN_CELLS_PER_RADIUS = 12
MIN_CELLS_PER_WAVELENGTH_AT_4KHZ = 10
_BUDGETS = tomllib.loads((ROOT / "docs" / "quality" / "budgets.toml").read_text(encoding="utf-8"))
LEVEL_THRESHOLD_DB: float = _BUDGETS["acoustics"]["conformance"]["level_tolerance_db"]
CUE_THRESHOLD_DB: float = _BUDGETS["acoustics"]["conformance"]["size_cue_tolerance_db"]
# ---- Implementation choices, not thresholds ------------------------------------------
PEAK_HZ = 2500.0
#: Fixed frequencies at which every level is evaluated (amendment 2, 2026-11-17): exact
#: transforms of the recordings, so levels do not depend on where FFT bins fall.
BAND_FREQUENCIES_HZ = np.linspace(cn.CLICK_BAND_HZ[0], cn.CLICK_BAND_HZ[1], 41)
#: Re-running must reproduce stored levels to this precision (numerical, not perceptual).
REPRODUCIBILITY_DB: float = _BUDGETS["experiments"]["reproducibility_db"]


def reference_grid(radius_m: float) -> tuple[int, float]:
    """Cells per radius and cell size meeting both pre-registered resolution rules."""
    wavelength = SPEED_OF_SOUND / 4000.0
    cells = max(
        MIN_CELLS_PER_RADIUS,
        math.ceil(radius_m * MIN_CELLS_PER_WAVELENGTH_AT_4KHZ / wavelength),
    )
    return cells, radius_m / (cells + fdtd.DISK_EDGE_OFFSET_CELLS)


def run_case(diameter_cm: float, distance_cm: float) -> dict[str, Any]:
    """Compute reference and engine levels for one disc at one distance."""
    radius = diameter_cm / 200.0
    cells, h = reference_grid(radius)
    started = time.perf_counter()
    ref = fdtd.monostatic_echo_ratio(
        "disk",
        distance_cells=round(distance_cm / 100.0 / h + 0.5),
        radius_cells=cells,
        h=h,
        peak_frequency_hz=PEAK_HZ,
        frequencies_hz=BAND_FREQUENCIES_HZ,
    )
    f = ref.frequency_hz
    target = cn.Disk(ref.radius, ref.distance)
    engine = cn.PlateEngineModel().echo_ratio(target, f)
    seconds = time.perf_counter() - started
    ka = 2.0 * math.pi * f * ref.radius / SPEED_OF_SOUND
    return {
        "diameter_cm": diameter_cm,
        "distance_cm": distance_cm,
        "acoustic_radius_m": ref.radius,
        "acoustic_distance_m": ref.distance,
        "cells_per_radius": cells,
        "ka_range": [round(float(ka.min()), 3), round(float(ka.max()), 3)],
        "n_frequencies": int(f.size),
        "reference_level_db": round(cn.band_level_db(ref.ratio), 4),
        "engine_level_db": round(cn.band_level_db(engine), 4),
        "seconds": round(seconds, 1),
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the pre-registered metrics and decision rule."""
    by_key = {(c["diameter_cm"], c["distance_cm"]): c for c in cases}
    for c in cases:
        c["level_error_db"] = round(c["engine_level_db"] - c["reference_level_db"], 4)
        c["level_pass"] = abs(c["level_error_db"]) <= LEVEL_THRESHOLD_DB
    cues = []
    for distance in DISTANCES_CM:
        ref_disc = by_key[(REFERENCE_DIAMETER_CM, distance)]
        for diameter in DIAMETERS_CM:
            if diameter == REFERENCE_DIAMETER_CM:
                continue
            other = by_key[(diameter, distance)]
            wave = ref_disc["reference_level_db"] - other["reference_level_db"]
            model = ref_disc["engine_level_db"] - other["engine_level_db"]
            cues.append(
                {
                    "distance_cm": distance,
                    "comparison_diameter_cm": diameter,
                    "reference_cue_db": round(wave, 4),
                    "engine_cue_db": round(model, 4),
                    "cue_error_db": round(model - wave, 4),
                    "cue_pass": abs(model - wave) <= CUE_THRESHOLD_DB,
                }
            )
    passed = {(c["diameter_cm"], c["distance_cm"]): c["level_pass"] for c in cases}
    for q in cues:
        # Decision rule, read at the level of a trial (reference disc against one
        # comparison disc at one distance): the engine is used only if both discs pass
        # metric 1 and the pair passes metric 2. See the protocol's amendment of
        # 2026-11-16 for why this reading was recorded.
        q["trial_uses_engine"] = bool(
            q["cue_pass"]
            and passed[(REFERENCE_DIAMETER_CM, q["distance_cm"])]
            and passed[(q["comparison_diameter_cm"], q["distance_cm"])]
        )
    return {
        "experiment": "EXP-0003",
        "thresholds": {"level_db": LEVEL_THRESHOLD_DB, "cue_db": CUE_THRESHOLD_DB},
        "engine": cn.PlateEngineModel().name,
        "cases": cases,
        "cues": cues,
        "summary": {
            "level_pass": sum(c["level_pass"] for c in cases),
            "cue_pass": sum(q["cue_pass"] for q in cues),
            "trials_using_engine": sum(q["trial_uses_engine"] for q in cues),
            "n_cases": len(cases),
            "n_cues": len(cues),
        },
    }


def run_all() -> dict[str, Any]:
    """Run every case of the protocol."""
    cases = []
    for distance in DISTANCES_CM:
        for diameter in DIAMETERS_CM:
            case = run_case(diameter, distance)
            print(
                f"{diameter:5.1f} cm at {distance:4.0f} cm: reference "
                f"{case['reference_level_db']:+7.2f} dB, engine {case['engine_level_db']:+7.2f} dB "
                f"({case['seconds']} s)",
                flush=True,
            )
            cases.append(case)
    return evaluate(cases)


def compare(fresh: dict[str, Any], stored: dict[str, Any]) -> list[str]:
    """Return differences between a fresh run and the stored results."""
    problems = []
    stored_cases = {(c["diameter_cm"], c["distance_cm"]): c for c in stored["cases"]}
    for c in fresh["cases"]:
        old = stored_cases.get((c["diameter_cm"], c["distance_cm"]))
        if old is None:
            problems.append(f"case {c['diameter_cm']} cm at {c['distance_cm']} cm is new")
            continue
        for key in ("reference_level_db", "engine_level_db"):
            if abs(c[key] - old[key]) > REPRODUCIBILITY_DB:
                problems.append(
                    f"{c['diameter_cm']} cm at {c['distance_cm']} cm: {key} {c[key]} "
                    f"differs from stored {old[key]}"
                )
        if c["level_pass"] != old["level_pass"]:
            problems.append(f"{c['diameter_cm']} cm at {c['distance_cm']} cm: verdict changed")
    return problems


def main(argv: list[str] | None = None) -> int:
    """Run EXP-0003, then write or check the results file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare with the stored results")
    args = parser.parse_args(argv)
    fresh = run_all()
    s = fresh["summary"]
    print(
        f"levels within {LEVEL_THRESHOLD_DB} dB: {s['level_pass']}/{s['n_cases']}; "
        f"cues within {CUE_THRESHOLD_DB} dB: {s['cue_pass']}/{s['n_cues']}; "
        f"trials using the engine: {s['trials_using_engine']}/{s['n_cues']}"
    )
    if args.check:
        problems = compare(fresh, json.loads(RESULTS.read_text(encoding="utf-8")))
        for p in problems:
            print(f"EXP-0003: {p}", file=sys.stderr)
        return 1 if problems else 0
    for c in fresh["cases"]:
        c.pop("seconds")
    RESULTS.write_text(json.dumps(fresh, indent=2) + "\n", encoding="utf-8")
    print(f"written: {RESULTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
