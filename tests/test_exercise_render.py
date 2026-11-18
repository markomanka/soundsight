# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for exercise trial rendering (candidate R1 of EXP-0005).

Contributed by Kimi (kimi.ai) on 2026-11-18 and revised on review: the assertion that a
disc echoes less than a wall was replaced (a disc about one Fresnel zone wide echoes
louder, as EXP-0003 measured), the energy inequality by an exact fidelity test, and the
timing test moved to EXP-0005's cost measurement (CI machines vary too much for a unit
test). See docs/experiments/EXP-0005-exercise-rendering.md.
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from soundsight.acoustics import canonical as cn
from soundsight.acoustics.engine import plate_echo
from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND
from soundsight.click.synth import synth_click
from soundsight.exercise.render import (
    BAND_FREQUENCIES_HZ,
    PEAK_NORMALIZATION,
    disc_plate,
    format_trial_text,
    render_disc_trial,
    to_dict,
)

#: An explicit click reference distance for the tests (any positive value would do).
R_REF = 0.5
PROTOCOL_DISTANCES_M = (0.33, 0.66, 0.99)
LARGEST_DIAMETER_M = 0.254
#: A rendered delay must sit within this many samples of the round-trip time 2 d / c.
DELAY_TOLERANCE_S = 3.0 / 48_000.0


def render(diameter: float, distance: float, **kw: object):  # type: ignore[no-untyped-def]
    return render_disc_trial(diameter, distance, click_reference_distance_m=R_REF, **kw)  # type: ignore[arg-type]


def test_render_is_deterministic() -> None:
    first, first_report = render(0.175, 0.66)
    second, second_report = render(0.175, 0.66)
    assert np.array_equal(first.samples, second.samples)
    assert replace(first_report, render_seconds=0.0) == replace(second_report, render_seconds=0.0)


@pytest.mark.parametrize("distance_m", PROTOCOL_DISTANCES_M)
def test_echo_delay_is_the_round_trip(distance_m: float) -> None:
    """The strongest arrival is the mirror echo at 2 d / c: the distance cue."""
    _, report = render(0.175, distance_m)
    assert abs(report.echo_delay_s - 2.0 * distance_m / SPEED_OF_SOUND) <= DELAY_TOLERANCE_S
    assert abs(report.echo_distance_m - distance_m) <= 0.02


def test_a_disc_one_fresnel_zone_wide_echoes_louder_than_a_wall() -> None:
    """The 25.4 cm disc at 33 cm: rim and centre add up (EXP-0003 measured +6.6 dB with
    the wave solver); a small disc far away echoes far less than a wall."""
    _, big = render(LARGEST_DIAMETER_M, 0.33)
    assert big.echo_ratio_db > 5.0
    model = cn.PlateEngineModel(n_sides=32)
    expected = cn.band_level_db(model.echo_ratio(cn.Disk(0.127, 0.33), BAND_FREQUENCIES_HZ))
    assert big.echo_ratio_db == pytest.approx(expected, abs=1e-9)
    _, small = render(0.051, 0.99)
    assert small.echo_ratio_db < -20.0


def test_echo_in_the_audio_is_the_click_times_the_engine_response() -> None:
    """Fidelity: undo the normalization, remove the click, and what remains must be the
    click filtered by the engine's exact response, scaled to the click's reference."""
    recording, report = render(0.175, 0.66)
    fs = recording.sample_rate
    click = synth_click(fs)
    mix = recording.channel(0) / report.normalization_gain
    echo = mix.copy()
    echo[: click.size] -= click
    n = echo.size
    f = np.fft.rfftfreq(n, 1 / fs)
    band = (f >= 2000) & (f <= 4000)
    arrivals = plate_echo(disc_plate(0.175, 0.66), (0, 0, 0), f_max=fs / 2)
    expected = np.fft.rfft(click, n=n)[band] * R_REF * arrivals.frequency_response(f[band])
    got = np.fft.rfft(echo)[band]
    assert np.max(np.abs(got - expected)) < 1e-4 * np.max(np.abs(expected))


def test_reference_distance_sets_the_echo_to_click_level() -> None:
    """Doubling the distance the click stands for doubles the echo relative to it."""
    near = render_disc_trial(0.175, 0.66, click_reference_distance_m=0.25)[1]
    far = render_disc_trial(0.175, 0.66, click_reference_distance_m=0.5)[1]
    assert far.echo_band_level_db - near.echo_band_level_db == pytest.approx(
        20 * math.log10(2), abs=1e-9
    )
    assert far.echo_ratio_db == near.echo_ratio_db  # the physics of the disc is unchanged


@settings(max_examples=10, deadline=None)
@given(distance_m=st.floats(min_value=0.4, max_value=1.2))
def test_further_discs_echo_later_and_quieter(distance_m: float) -> None:
    """For a 17.5 cm disc over this range the disc stays smaller than the first Fresnel
    zone at 3 kHz, so its echo weakens with distance. Not a law for large discs, whose
    echo oscillates with distance as Fresnel zones are added."""
    near, near_report = render(0.175, 0.33)
    far, far_report = render(0.175, distance_m)
    assert far_report.echo_delay_s > near_report.echo_delay_s
    assert far_report.echo_band_level_db < near_report.echo_band_level_db
    assert near.duration_s <= far.duration_s


def test_normalization_and_custom_click() -> None:
    recording, report = render(0.135, 0.66, click=0.3 * synth_click(48_000))
    assert np.max(np.abs(recording.samples)) == pytest.approx(PEAK_NORMALIZATION)
    assert report.n_specular == 1
    assert report.n_arrivals > 1


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"click_reference_distance_m": 0.0}, "click_reference_distance_m"),
        ({"click_reference_distance_m": R_REF, "sample_rate": 0}, "sample_rate"),
        ({"click_reference_distance_m": R_REF, "click": np.array([np.nan])}, "finite"),
        (
            {"click_reference_distance_m": R_REF, "click": np.ones(10), "click_params": object()},
            "either",
        ),
    ],
)
def test_invalid_arguments(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        render_disc_trial(0.175, 0.66, **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(("diameter", "distance"), [(0.0, 0.66), (0.175, -1.0)])
def test_invalid_disc(diameter: float, distance: float) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        disc_plate(diameter, distance)


def test_text_report_is_linear_plain_and_complete() -> None:
    _, report = render(0.175, 0.66)
    text = format_trial_text(report, "trial.wav", budget_s=120.0)
    assert text.isascii()
    assert "17.5 centimetres across" in text
    assert "milliseconds after the click" in text
    assert "than a wall at the same distance" not in text  # phrased as a comparison
    assert "Compared with a wall at the same distance" in text
    assert "the budget is 120 seconds" in text
    assert all(line.endswith(".") for line in text.strip().split("\n"))
    data = to_dict(report)
    assert data["click_reference_distance_m"] == R_REF
    assert set(data) >= {"echo_delay_s", "echo_band_level_db", "echo_ratio_db"}
