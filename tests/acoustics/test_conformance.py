# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Conformance matrix: which model answers which canonical problem correctly.

This file is the executable record behind docs/decisions/0002-acoustic-engine.md.
Every (model, problem) pair has a declared verdict. PASS pairs must stay within the
tolerance; FAIL pairs are strict expected failures, so the suite also breaks if a
model starts passing where the record says it cannot. To admit a new engine, wrap it
as an EchoModel, add it to MODELS and declare its verdicts.

Tolerances are in decibels of band level because about 1 dB is the smallest level
difference listeners notice.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from soundsight.acoustics import canonical as cn
from soundsight.acoustics.reference import fdtd
from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND as C

PASS, FAIL = "pass", "fail"

MODELS: dict[str, cn.EchoModel] = {
    m.name: m
    for m in (
        cn.SpecularModel(),
        cn.KirchhoffModel(),
        cn.EdgeDiffractionModel(),
        cn.CompactModel(),
        cn.PlateEngineModel(),
    )
}

#: Thresholds come from the single versioned source, never from this file.
BUDGETS = tomllib.loads(
    (Path(__file__).resolve().parents[2] / "docs" / "quality" / "budgets.toml").read_text(
        encoding="utf-8"
    )
)["acoustics"]
LEVEL_TOLERANCE_DB: float = BUDGETS["conformance"]["level_tolerance_db"]
CUE_TOLERANCE_DB: float = BUDGETS["conformance"]["size_cue_tolerance_db"]


def _click_band(run: fdtd.EchoRatio) -> np.ndarray:
    return (run.frequency_hz >= cn.CLICK_BAND_HZ[0]) & (run.frequency_hz <= cn.CLICK_BAND_HZ[1])


def _level_error(model: cn.EchoModel, run: fdtd.EchoRatio) -> float:
    band = _click_band(run)
    target = cn.Disk(run.radius, run.distance)
    modelled = cn.band_level_db(model.echo_ratio(target, run.frequency_hz[band]))
    return modelled - cn.band_level_db(run.ratio[band])


def _check(verdict: str, passed: bool, detail: str) -> None:
    if verdict == FAIL:
        if passed:
            pytest.fail(f"declared FAIL but it passes ({detail}): update the conformance record")
        pytest.xfail(f"known limit of this model ({detail})")
    assert passed, detail


def test_reference_models_satisfy_the_protocol() -> None:
    for model in MODELS.values():
        assert isinstance(model, cn.EchoModel)


@pytest.mark.parametrize("name", ["specular", "kirchhoff", "edge-diffraction", "engine"])
def test_wall_echoes_like_a_wall(name: str) -> None:
    ratio = MODELS[name].echo_ratio(cn.Wall(1.0), [500.0, 3000.0])
    np.testing.assert_array_equal(ratio, np.ones(2))


# ---------------------------------------------------------------- disk: absolute level
@pytest.mark.parametrize(
    ("name", "fixture", "verdict"),
    [
        ("specular", "disk_5cm", FAIL),  # ignores size: about 16 dB too loud
        ("specular", "disk_10cm", FAIL),  # about 5 dB too loud
        ("kirchhoff", "disk_5cm", FAIL),  # about 1.2 dB too quiet: rim coefficient too small
        ("kirchhoff", "disk_10cm", PASS),
        ("edge-diffraction", "disk_5cm", PASS),
        ("edge-diffraction", "disk_10cm", PASS),
        ("compact", "disk_10cm", FAIL),  # long-wavelength formula used far outside its range
        ("engine", "disk_5cm", PASS),  # about -0.8 dB
        ("engine", "disk_10cm", PASS),
    ],
)
def test_disk_echo_level_in_click_band(
    name: str, fixture: str, verdict: str, request: pytest.FixtureRequest
) -> None:
    error = _level_error(MODELS[name], request.getfixturevalue(fixture))
    _check(verdict, abs(error) <= LEVEL_TOLERANCE_DB, f"level error {error:+.2f} dB")


# ---------------------------------------------------------------- disk: the size cue
@pytest.mark.parametrize(
    ("name", "verdict"),
    [
        ("specular", FAIL),  # no size cue at all: the reason pure beams are rejected
        ("kirchhoff", PASS),
        ("edge-diffraction", PASS),
        ("compact", FAIL),
        ("engine", PASS),
    ],
)
def test_size_cue_between_5_and_10_cm_disks(
    name: str, verdict: str, disk_5cm: fdtd.EchoRatio, disk_10cm: fdtd.EchoRatio
) -> None:
    def cue(level: Callable[[fdtd.EchoRatio], float]) -> float:
        return level(disk_10cm) - level(disk_5cm)

    reference = cue(lambda run: cn.band_level_db(run.ratio[_click_band(run)]))
    assert reference == pytest.approx(10.6, abs=0.5)  # doubling the size: about +10.6 dB
    model = MODELS[name]
    modelled = reference + cue(lambda run: _level_error(model, run))
    _check(
        verdict,
        abs(modelled - reference) <= CUE_TOLERANCE_DB,
        f"size cue {modelled:+.2f} dB, wave solver {reference:+.2f} dB",
    )


# ---------------------------------------------------------------- disk: spectrum shape
def _spectrum_error(
    model: cn.EchoModel, run: fdtd.EchoRatio, ka_min: float, ka_max: float
) -> float:
    ka = 2 * np.pi * run.frequency_hz * run.radius / C
    sel = (ka >= ka_min) & (ka <= ka_max)
    assert sel.sum() >= 3
    modelled = model.echo_ratio(cn.Disk(run.radius, run.distance), run.frequency_hz[sel])
    return float((np.abs(run.ratio[sel] - modelled) / np.abs(run.ratio[sel])).mean())


@pytest.mark.parametrize("name", ["edge-diffraction", "engine"])
def test_edge_diffraction_tracks_the_spectrum_of_a_large_disk(
    name: str, disk_wide: fdtd.EchoRatio
) -> None:
    edge = _spectrum_error(MODELS[name], disk_wide, 5.0, 100.0)
    kirchhoff = _spectrum_error(MODELS["kirchhoff"], disk_wide, 5.0, 100.0)
    # Complex error, magnitude and phase, against the wave solver.
    assert edge < BUDGETS["conformance"]["large_disk_spectrum_error"]
    assert kirchhoff > 2.0 * edge  # the correct rim coefficient is what makes the difference


@pytest.mark.parametrize("name", ["edge-diffraction", "engine"])
def test_edge_diffraction_breaks_down_for_small_disks(
    name: str, disk_compact: fdtd.EchoRatio
) -> None:
    """Below ka of about 1 first-order diffraction fails and the compact model takes over.

    For the engine this is not an asymptotic breakdown but a missing physical effect:
    a small disk is crossed rim to rim many times per period (second-order diffraction).
    """
    edge = _spectrum_error(MODELS[name], disk_compact, 0.0, 0.5)
    compact = _spectrum_error(MODELS["compact"], disk_compact, 0.0, 0.5)
    assert compact < BUDGETS["conformance"]["compact_disk_spectrum_error"]
    assert edge > 0.5


# ---------------------------------------------------------------- disk: the known gap
@pytest.mark.parametrize("name", ["compact", "edge-diffraction", "kirchhoff", "engine"])
def test_no_simple_model_covers_disks_about_a_wavelength_around(
    name: str, disk_transition: fdtd.EchoRatio
) -> None:
    """Between ka of about 0.75 and 1.5 every current model is declared FAIL (ADR 0002).

    When a model that closes this gap is added, declare it PASS here.
    """
    run = disk_transition
    ka = 2 * np.pi * run.frequency_hz * run.radius / C
    sel = (ka >= 1.0 - 1e-9) & (ka <= 1.5 + 1e-9)
    assert sel.sum() == 11
    target = cn.Disk(run.radius, run.distance)
    error = cn.band_level_db(
        MODELS[name].echo_ratio(target, run.frequency_hz[sel])
    ) - cn.band_level_db(run.ratio[sel])
    _check(FAIL, abs(error) <= LEVEL_TOLERANCE_DB, f"level error {error:+.2f} dB at ka 1.0-1.5")


# ---------------------------------------------------------------- sphere (exact reference)
@pytest.mark.parametrize(
    ("name", "ka_range", "verdict"),
    [
        ("specular", (40.0, 80.0), PASS),  # a large sphere is a convex mirror
        ("specular", (0.1, 0.3), FAIL),  # a small one is not: about 23 dB too loud
        ("compact", (0.1, 0.3), PASS),
        ("compact", (40.0, 80.0), FAIL),
    ],
)
def test_sphere_echo_level(name: str, ka_range: tuple[float, float], verdict: str) -> None:
    target = cn.Sphere(radius=0.1, distance=1.0)
    f = np.linspace(*ka_range, 200) * C / (2 * np.pi * target.radius)
    error = cn.band_level_db(MODELS[name].echo_ratio(target, f)) - cn.band_level_db(
        cn.exact_echo_ratio(target, f)
    )
    _check(verdict, abs(error) <= LEVEL_TOLERANCE_DB, f"level error {error:+.2f} dB")


# ---------------------------------------------------------------- engine against theory
def test_engine_reproduces_first_order_closed_form_on_axis() -> None:
    """Two independent derivations agree: the general edge integral of the engine, and
    the closed form with the exact rim coefficient (they share no code)."""
    target = cn.Disk(radius=0.1, distance=0.7)
    f = np.linspace(0.3, 30.0, 60) * C / (2 * np.pi * target.radius)
    engine = MODELS["engine"].echo_ratio(target, f)
    closed = MODELS["edge-diffraction"].echo_ratio(target, f)
    assert float(np.max(np.abs(engine - closed))) < 2e-3


# ---------------------------------------------------------------- plumbing
@pytest.mark.parametrize(
    ("name", "target"),
    [
        ("kirchhoff", cn.Sphere(0.1, 1.0)),
        ("edge-diffraction", cn.Sphere(0.1, 1.0)),
        ("compact", cn.Wall(1.0)),
        ("engine", cn.Sphere(0.1, 1.0)),
    ],
)
def test_models_refuse_targets_they_cannot_handle(name: str, target: cn.Target) -> None:
    with pytest.raises(cn.UnsupportedTargetError, match="has no model"):
        MODELS[name].echo_ratio(target, [1000.0])


def test_click_band_matches_the_budgets_file() -> None:
    band = BUDGETS["click_band_hz"]
    assert (band["low"], band["high"]) == cn.CLICK_BAND_HZ


def test_exact_wall_and_band_level() -> None:
    np.testing.assert_array_equal(cn.exact_echo_ratio(cn.Wall(2.0), [100.0, 200.0]), np.ones(2))
    assert cn.band_level_db(np.array([1.0, 1.0])) == 0.0
    assert cn.band_level_db(np.array([0.1 + 0j])) == pytest.approx(-20.0)
    assert cn.band_level_db(np.zeros(3, dtype=complex)) == float("-inf")
    weighted = cn.band_level_db(np.array([1.0, 0.0]), weights=np.array([1.0, 3.0]))
    assert weighted == pytest.approx(10 * np.log10(0.25))
