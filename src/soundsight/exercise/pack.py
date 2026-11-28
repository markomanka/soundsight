# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Exercise pack v0: which of two discs is larger? For co-design, not yet for training.

The task follows the size-discrimination task of Norman et al. (2021, literature A3): a
25.4 cm reference disc against discs of 5.1, 9.0, 13.5, 17.5 and 22.9 cm, at 33, 66 and
99 cm. It is an **adaptation**: in the study two discs were presented at once, above and
below ear height; here the engine renders one disc straight ahead, for one ear, so each
trial plays two click-and-echo intervals in sequence and asks which disc was larger.

Echoes come from R3 (EXP-0006), the per-disc cache of diffraction of all orders. The
caches of the 18 discs are stored with the package, so a pack is generated in seconds.
One gain applies to the whole pack: the level difference between two echoes is the cue
the trainee listens for, and normalizing files one by one would distort it.

Open before anyone trains with it: the level of the echo relative to the click depends
on what the click recording stands for (``click_reference_distance_m``) and on the
mouth-to-ear path, which must be calibrated with an echolocation instructor or researcher.
"""

from __future__ import annotations

import hashlib
import json
from importlib import resources
from pathlib import Path
from typing import Any

import numpy as np

from soundsight import __version__
from soundsight.audio import FloatArray, from_array, write_wav
from soundsight.click.synth import synth_click
from soundsight.exercise import render_cached as r3

SAMPLE_RATE = 48_000
REFERENCE_DIAMETER_CM = 25.4
COMPARISON_DIAMETERS_CM = (5.1, 9.0, 13.5, 17.5, 22.9)
DISTANCES_CM = (33.0, 66.0, 99.0)
#: Silence before the first interval, between the two intervals, and after the second.
LEAD_S, GAP_S, TAIL_S = 0.1, 0.6, 0.2
#: Peak of the loudest file in the pack.
PACK_PEAK = 0.9
PACK_NAME = "size-discrimination-v0"
STATUS = (
    "For co-design: an adaptation of a published task, with the echo level provisionally "
    "calibrated. Not a validated training protocol."
)
CACHE_RESOURCE = "data/disc_echo_caches.json"


def load_caches(path: Path | None = None) -> dict[tuple[float, float], r3.DiscEchoCache]:
    """Read the stored disc caches, keyed by (diameter in cm, distance in cm)."""
    text = _resource(CACHE_RESOURCE) if path is None else path.read_text(encoding="utf-8")
    data = json.loads(text)
    if data["sample_rate"] != SAMPLE_RATE or data["window_s"] != r3.WINDOW_S:
        msg = "stored caches do not match the renderer's sample rate or window"
        raise ValueError(msg)
    f = np.asarray(data["frequency_hz"], dtype=np.float64)
    if not np.allclose(f, r3.cache_grid(SAMPLE_RATE)):
        msg = "stored caches do not match the renderer's frequency grid"
        raise ValueError(msg)
    out = {}
    for disc in data["discs"]:
        higher = np.asarray(disc["higher_re"]) + 1j * np.asarray(disc["higher_im"])
        key = (float(disc["diameter_cm"]), float(disc["distance_cm"]))
        out[key] = r3.DiscEchoCache(key[0] / 100, key[1] / 100, SAMPLE_RATE, f, higher, 0.0)
    return out


def build_cache_file(path: Path) -> None:
    """Recompute and write the 18 disc caches (slow: about half an hour)."""
    discs = []
    for dist in DISTANCES_CM:
        for d in (*COMPARISON_DIAMETERS_CM, REFERENCE_DIAMETER_CM):
            cache = r3.build_cache(d / 100, dist / 100, SAMPLE_RATE)
            discs.append(
                {
                    "diameter_cm": d,
                    "distance_cm": dist,
                    "higher_re": [float(x.real) for x in cache.higher],
                    "higher_im": [float(x.imag) for x in cache.higher],
                }
            )
    data = {
        "description": "Diffraction of order two and above for the 18 discs of the "
        "size-discrimination task (candidate R3 of EXP-0006).",
        "sample_rate": SAMPLE_RATE,
        "window_s": r3.WINDOW_S,
        "sides": 48,
        "frequency_hz": [float(x) for x in r3.cache_grid(SAMPLE_RATE)],
        "discs": discs,
    }
    path.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")


def interval(
    cache: r3.DiscEchoCache, click: FloatArray, click_reference_distance_m: float
) -> FloatArray:
    """One click and its echo from one disc, unnormalized."""
    ir = r3.cached_impulse_response(cache)
    n = click.size + ir.size - 1
    echo = np.fft.irfft(np.fft.rfft(click, n) * np.fft.rfft(ir, n), n) * click_reference_distance_m
    echo[: click.size] += click
    return np.asarray(echo, dtype=np.float64)


def trial_plan() -> list[dict[str, Any]]:
    """Return the 30 trials: each comparison disc against the reference, both orders."""
    plan: list[dict[str, Any]] = []
    for dist in DISTANCES_CM:
        for comp in COMPARISON_DIAMETERS_CM:
            for first, second in ((REFERENCE_DIAMETER_CM, comp), (comp, REFERENCE_DIAMETER_CM)):
                plan.append(
                    {
                        "distance_cm": dist,
                        "first_cm": first,
                        "second_cm": second,
                        "larger": 1 if first > second else 2,
                    }
                )
    for number, trial in enumerate(plan, start=1):
        trial["number"] = number
        trial["file"] = f"trial-{number:02d}.wav"
    return plan


def make_pack(
    out_dir: Path,
    *,
    click_reference_distance_m: float,
    click: FloatArray | None = None,
    caches: dict[tuple[float, float], r3.DiscEchoCache] | None = None,
) -> dict[str, Any]:
    """Render the pack into ``out_dir``: 30 WAV files, a manifest, a player and a readme."""
    if not click_reference_distance_m > 0.0:
        msg = f"click_reference_distance_m must be positive, got {click_reference_distance_m}"
        raise ValueError(msg)
    custom_click = click is not None
    click = synth_click(SAMPLE_RATE) if click is None else np.asarray(click, dtype=np.float64)
    if click.ndim != 1 or click.size == 0 or not np.all(np.isfinite(click)):
        msg = "click must be a non-empty finite 1-D array"
        raise ValueError(msg)
    caches = load_caches() if caches is None else caches
    intervals = {
        key: interval(cache, click, click_reference_distance_m) for key, cache in caches.items()
    }
    length = max(x.size for x in intervals.values())
    lead, gap, tail = (round(s * SAMPLE_RATE) for s in (LEAD_S, GAP_S, TAIL_S))
    plan = trial_plan()
    audio = []
    for t in plan:
        a, b = (
            intervals[(t["first_cm"], t["distance_cm"])],
            intervals[(t["second_cm"], t["distance_cm"])],
        )
        x = np.zeros(lead + 2 * length + gap + tail)
        x[lead : lead + a.size] = a
        start = lead + length + gap
        x[start : start + b.size] = b
        audio.append(x)
    gain = PACK_PEAK / max(float(np.max(np.abs(x))) for x in audio)
    out_dir.mkdir(parents=True, exist_ok=True)
    for t, x in zip(plan, audio, strict=True):
        path = write_wav(out_dir / t["file"], from_array(x * gain, SAMPLE_RATE))
        t["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "pack": PACK_NAME,
        "status": STATUS,
        "soundsight_version": __version__,
        "task": "Which disc is larger, the first or the second? Adapted from the "
        "size-discrimination task of Norman et al. (2021).",
        "parameters": {
            "sample_rate": SAMPLE_RATE,
            "click_reference_distance_m": click_reference_distance_m,
            "click": "custom" if custom_click else "synthetic",
            "lead_s": LEAD_S,
            "gap_s": GAP_S,
            "tail_s": TAIL_S,
            "pack_gain": gain,
            "echo_model": "R3, diffraction of all orders from per-disc caches (EXP-0006)",
        },
        "trials": plan,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    embedded = json.dumps(manifest).replace("</", "<\\/")
    player = _resource("player.html").replace("__MANIFEST__", embedded)
    (out_dir / "player.html").write_text(player, encoding="utf-8")
    (out_dir / "README.txt").write_text(_readme(manifest), encoding="utf-8")
    return manifest


def _resource(name: str) -> str:
    return resources.files("soundsight.exercise").joinpath(name).read_text(encoding="utf-8")


def _readme(manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            "SoundSight exercise pack: which disc is larger?",
            "",
            manifest["status"],
            "",
            "To start, open player.html in a web browser. It works with screen readers and needs",
            "no installation and no internet connection. Use headphones.",
            "",
            "Each trial plays two clicks, each followed by its echo from a disc in front of you.",
            "Decide which disc was larger: the first or the second.",
            "Keys: P plays the trial, 1 means the first was larger, 2 means the second was larger.",
            "You can play a trial as often as you like before answering.",
            "At the end, the player offers to save your answers as a file. Please send that file",
            "back, together with anything that was difficult, unclear or annoying.",
            "",
            f"Pack {manifest['pack']}, made with SoundSight {manifest['soundsight_version']}.",
            "",
        ]
    )
