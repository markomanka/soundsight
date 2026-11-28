# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Exercise pack v0 (size discrimination, for co-design) and its player."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
import pytest

from soundsight.acoustics.canonical import band_level_db
from soundsight.audio import read_wav
from soundsight.cli import EXIT_OK, main
from soundsight.exercise import pack
from soundsight.exercise import render_all_orders as r2
from soundsight.exercise import render_cached as r3


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:  # type: ignore[type-arg]
    out = tmp_path_factory.mktemp("pack")
    return out, pack.make_pack(out, click_reference_distance_m=0.5)


def test_stored_caches_cover_the_task_and_match_the_renderer() -> None:
    caches = pack.load_caches()
    expected = {
        (d, dist)
        for dist in pack.DISTANCES_CM
        for d in (*pack.COMPARISON_DIAMETERS_CM, pack.REFERENCE_DIAMETER_CM)
    }
    assert set(caches) == expected
    assert all(c.frequency_hz.size == r3.cache_grid(pack.SAMPLE_RATE).size for c in caches.values())


def test_stored_cache_matches_a_fresh_computation() -> None:
    """The stored data are what R3 computes (smallest disc, cheapest to recompute)."""
    stored = pack.load_caches()[(5.1, 99.0)]
    fresh = r3.build_cache(0.051, 0.99, pack.SAMPLE_RATE)
    np.testing.assert_allclose(stored.higher, fresh.higher, rtol=1e-9, atol=1e-12)


def test_plan_is_balanced() -> None:
    plan = pack.trial_plan()
    assert len(plan) == 30
    assert sum(t["larger"] == 1 for t in plan) == 15  # the larger disc comes first half the time
    assert all(max(t["first_cm"], t["second_cm"]) == pack.REFERENCE_DIAMETER_CM for t in plan)


def test_files_match_the_manifest_and_regenerate_identically(built, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    out, manifest = built
    for t in manifest["trials"]:
        assert hashlib.sha256((out / t["file"]).read_bytes()).hexdigest() == t["sha256"]
    again = pack.make_pack(tmp_path, click_reference_distance_m=0.5)
    assert [t["sha256"] for t in again["trials"]] == [t["sha256"] for t in manifest["trials"]]
    assert manifest["parameters"]["click"] == "synthetic"


def test_the_larger_disc_echoes_louder_in_every_trial(built) -> None:  # type: ignore[no-untyped-def]
    """One gain for the whole pack keeps the cue: the larger disc's echo is louder."""
    out, manifest = built
    lead = round(pack.LEAD_S * pack.SAMPLE_RATE)
    gap = round(pack.GAP_S * pack.SAMPLE_RATE)
    f = np.linspace(2000.0, 4000.0, 41)
    # Before the earliest echo (1.9 ms at 33 cm), so only the click is compared.
    click_samples = round(0.0015 * pack.SAMPLE_RATE)
    for t in manifest["trials"]:
        x = read_wav(out / t["file"]).channel(0)
        half = (x.size - lead - gap - round(pack.TAIL_S * pack.SAMPLE_RATE)) // 2
        a = x[lead : lead + half]
        b = x[lead + half + gap : lead + 2 * half + gap]
        assert np.max(np.abs(a[:click_samples])) == pytest.approx(
            np.max(np.abs(b[:click_samples])), rel=1e-3
        )
        onset = int(2 * t["distance_cm"] / 100 / 343 * pack.SAMPLE_RATE) - 20
        level_a = band_level_db(r2.dtft(a[onset:], pack.SAMPLE_RATE, f))
        level_b = band_level_db(r2.dtft(b[onset:], pack.SAMPLE_RATE, f))
        assert (level_a > level_b) == (t["larger"] == 1)


class _Collect(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.buttons: list[str] = []
        self.live = False
        self.scripts: list[str] = []
        self._in: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if a.get("role") == "status" and a.get("aria-live") == "polite":
            self.live = True
        self._in = tag

    def handle_data(self, data: str) -> None:
        if self._in == "button" and data.strip():
            self.buttons.append(data.strip())
        if self._in == "script":
            self.scripts.append(data)

    def handle_endtag(self, tag: str) -> None:  # noqa: ARG002 - any end tag ends the element
        self._in = None


def test_player_is_accessible_and_carries_the_manifest(built) -> None:  # type: ignore[no-untyped-def]
    out, _ = built
    html = (out / "player.html").read_text(encoding="utf-8")
    parsed = _Collect()
    parsed.feed(html)
    assert parsed.live  # announcements reach screen readers
    assert {
        "Start",
        "Play the trial (P)",
        "The first disc was larger (1)",
        "The second disc was larger (2)",
        "Save my answers",
    } <= set(parsed.buttons)
    embedded = re.search(
        r'<script id="manifest" type="application/json">(.*?)</script>', html, re.S
    )
    assert embedded is not None
    assert json.loads(embedded.group(1)) == json.loads((out / "manifest.json").read_text())
    assert 'lang="en"' in html


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_player_script_is_valid_javascript(built, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    out, _ = built
    html = (out / "player.html").read_text(encoding="utf-8")
    script = html.split("<script>")[1].split("</script>")[0]
    js = tmp_path / "player.js"
    js.write_text(script, encoding="utf-8")
    node = shutil.which("node")
    assert node is not None
    result = subprocess.run([node, "--check", str(js)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(["exercise", "pack", str(tmp_path / "p"), "--click-reference-distance", "0.5"])
        == EXIT_OK
    )
    assert (tmp_path / "p" / "player.html").is_file()
    assert "Open player.html" in capsys.readouterr().out
    assert main(["click", "synth", str(tmp_path / "c.wav"), "--sample-rate", "16000"]) == EXIT_OK
    code = main(
        [
            "exercise",
            "pack",
            str(tmp_path / "q"),
            "--click-reference-distance",
            "0.5",
            "--click",
            str(tmp_path / "c.wav"),
        ]
    )
    assert code == 2  # wrong sample rate
    with pytest.raises(ValueError, match="positive"):
        pack.make_pack(tmp_path / "r", click_reference_distance_m=0.0)
