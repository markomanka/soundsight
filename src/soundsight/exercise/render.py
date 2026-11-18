# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
r"""Render a single echo-acoustic exercise trial: a click, a disc, its echo.

Contributed by Kimi (kimi.ai) on 2026-11-18 and integrated after review as candidate R1
of EXP-0005 (docs/experiments/EXP-0005-exercise-rendering.md), which lists every change
made on review and the evidence for it.

This is the bridge from the acoustic engine (docs/decisions/0002-acoustic-engine.md)
to the first exercise pack of the roadmap (stage S2): the size-discrimination discs
of the training study (A3), rendered in advance at 48 kHz and played over
headphones. The trial audio is the click followed by the echo it would return from
a rigid disc of a given diameter at a given distance, at the physically correct
relative level. The whole file is peak-normalized with one gain, so the
echo-to-click relative level, the quantity the trainee learns, is preserved.

The relative level needs a reference. The click signal stands for the sound at a
known distance from the mouth, ``click_reference_distance_m``: the distance at which
it was recorded, as the click coach records it. The echo is scaled to the same
reference. (What a listener hears directly at the ear differs again by the mouth's
directivity and the mouth-to-ear path; calibrating that is an open item of EXP-0005.)

This renderer (R1) uses first-order diffraction, engine increment 1. EXP-0003 showed
that first order is not valid for the 5.1 cm disc at any protocol distance nor for the
9.0 cm disc at 66 and 99 cm; EXP-0004 chose diffraction of all orders (C2) for those.
Rendering trials with C2 within a cost budget is the question of EXP-0005, in which R1
is the baseline. Monaural; one rigid disc facing the listener, no occlusion, no room.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
from scipy.signal import fftconvolve

from soundsight.acoustics import engine as _engine
from soundsight.acoustics.canonical import CLICK_BAND_HZ, band_level_db
from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND, plane_echo
from soundsight.audio import FloatArray, Recording, from_array
from soundsight.click.synth import ClickParameters, synth_click

#: The trial discs are approximated by regular polygons. With 32 sides first-order
#: diffraction is within about 4e-4 of the converged disc (the engine's polygon
#: convergence test: errors fall four times per doubling, 1.8e-4 at 48 sides).
DEFAULT_DISC_SIDES = 32
#: Silence kept after the last arrival, so late diffraction components are not cut.
IR_MARGIN_S = 0.005
#: Peak the normalized file is scaled to, leaving headroom for playback.
PEAK_NORMALIZATION = 0.95
#: Band levels are evaluated at fixed frequencies, never at FFT bins (EXP-0003,
#: amendment 2: bins move with the recording length and shift band averages).
BAND_FREQUENCIES_HZ = np.linspace(CLICK_BAND_HZ[0], CLICK_BAND_HZ[1], 41)


@dataclass(frozen=True)
class TrialReport:
    """Facts about one rendered trial, for exercise players, reports and tests.

    ``echo_band_level_db`` is relative to the click at its reference distance (0 dB);
    ``echo_ratio_db`` is relative to a rigid wall at the disc's distance, the quantity
    of EXP-0003, and can be positive: a disc about one Fresnel zone wide echoes louder
    than a wall.
    """

    disc_diameter_m: float
    disc_distance_m: float
    echo_delay_s: float
    echo_distance_m: float
    echo_band_level_db: float
    echo_ratio_db: float
    click_reference_distance_m: float
    n_arrivals: int
    n_specular: int
    normalization_gain: float
    render_seconds: float


def disc_plate(
    diameter_m: float, distance_m: float, n_sides: int = DEFAULT_DISC_SIDES
) -> _engine.Plate:
    """Approximate the trial disc by a regular polygon facing the listener.

    The listener is at the origin, facing the positive z axis, so the disc's
    mirror side faces them.
    """
    if not diameter_m > 0.0:
        msg = f"diameter_m must be positive, got {diameter_m}"
        raise ValueError(msg)
    if not distance_m > 0.0:
        msg = f"distance_m must be positive, got {distance_m}"
        raise ValueError(msg)
    return _engine.Plate.regular(
        diameter_m / 2.0, n_sides, centre=(0.0, 0.0, distance_m), normal=(0.0, 0.0, 1.0)
    )


def render_disc_trial(
    diameter_m: float,
    distance_m: float,
    *,
    sample_rate: int = 48_000,
    click_reference_distance_m: float,
    click: FloatArray | None = None,
    click_params: ClickParameters | None = None,
    n_sides: int = DEFAULT_DISC_SIDES,
    c: float = SPEED_OF_SOUND,
) -> tuple[Recording, TrialReport]:
    """Render one size-discrimination trial and report the facts about it.

    Parameters
    ----------
    diameter_m, distance_m
        Disc diameter and one-way distance from the listener, in metres.
    sample_rate
        Sampling rate of the rendered file, in hertz.
    click_reference_distance_m
        Distance from the mouth at which the click signal represents the emitted
        sound (where it was recorded). It sets the echo-to-click level and has no
        default on purpose: a wrong value changes what the trainee learns.
    click
        The click to play, as a 1-D array. Defaults to the synthetic click of
        :func:`soundsight.click.synth.synth_click` with ``click_params``.
        A recording of the user's own click can replace it without any other
        change, which is how the roadmap's "the user's own recorded click"
        requirement is met.
    n_sides
        Polygon sides used to approximate the disc.
    c
        Speed of sound, in metres per second.

    Returns
    -------
    recording, report
        The normalized trial audio (click at time zero, echo after the
        round-trip delay) and the facts an exercise player or a report needs.

    Raises
    ------
    ValueError
        If the parameters are not positive, or an arrival is so early that the
        fractional-delay filter would be truncated (see
        :func:`soundsight.acoustics.engine.render`).
    """
    if sample_rate <= 0:
        msg = f"sample_rate must be positive, got {sample_rate}"
        raise ValueError(msg)
    if not click_reference_distance_m > 0.0:
        msg = f"click_reference_distance_m must be positive, got {click_reference_distance_m}"
        raise ValueError(msg)
    if click is None:
        click = synth_click(sample_rate, click_params)
    else:
        click = np.asarray(click, dtype=np.float64)
        if click.ndim != 1 or click.size == 0 or not np.all(np.isfinite(click)):
            msg = "click must be a non-empty finite 1-D array"
            raise ValueError(msg)
        if click_params is not None:
            msg = "pass either click or click_params, not both"
            raise ValueError(msg)
    started = time.perf_counter()
    plate = disc_plate(diameter_m, distance_m, n_sides)
    # Quadrature to the Nyquist frequency: limiting it to the click band would save
    # about 4 ms and was measured to change the response by at most 1e-4 (review notes).
    arrivals = _engine.plate_echo(plate, (0.0, 0.0, 0.0), f_max=sample_rate / 2.0, c=c)
    last_delay = float(arrivals.delays.max(initial=0.0))
    n_ir = max(2 * 32 + 2, math.ceil((last_delay + IR_MARGIN_S) * sample_rate))
    # The engine's echo is for a unit source (pressure 1/r at r metres). A click that
    # represents the pressure at r_ref comes from a source r_ref times stronger.
    impulse_response = _engine.render(arrivals, sample_rate, n_ir) * click_reference_distance_m
    echo = fftconvolve(click, impulse_response)
    mix = np.array(echo, dtype=np.float64, copy=True)
    mix[: click.size] += click
    peak = float(np.max(np.abs(mix)))
    gain = PEAK_NORMALIZATION / peak
    mix *= gain
    dominant = int(np.argmax(np.abs(arrivals.amplitudes)))
    response = arrivals.frequency_response(BAND_FREQUENCIES_HZ)
    band_level = band_level_db(response) + 20.0 * math.log10(click_reference_distance_m)
    wall = plane_echo(BAND_FREQUENCIES_HZ, distance_m, c)
    echo_ratio = band_level_db(response / wall)
    report = TrialReport(
        disc_diameter_m=diameter_m,
        disc_distance_m=distance_m,
        echo_delay_s=float(arrivals.delays[dominant]),
        echo_distance_m=c * float(arrivals.delays[dominant]) / 2.0,
        echo_band_level_db=band_level,
        echo_ratio_db=echo_ratio,
        click_reference_distance_m=click_reference_distance_m,
        n_arrivals=int(arrivals.delays.size),
        n_specular=len(arrivals.specular),
        normalization_gain=gain,
        render_seconds=time.perf_counter() - started,
    )
    return from_array(mix, sample_rate), report


def to_dict(report: TrialReport) -> dict[str, float | int]:
    """Return the report as plain values, for JSON output."""
    return {
        "disc_diameter_m": report.disc_diameter_m,
        "disc_distance_m": report.disc_distance_m,
        "echo_delay_s": report.echo_delay_s,
        "echo_distance_m": report.echo_distance_m,
        "echo_band_level_db": report.echo_band_level_db,
        "echo_ratio_db": report.echo_ratio_db,
        "click_reference_distance_m": report.click_reference_distance_m,
        "n_arrivals": report.n_arrivals,
        "n_specular": report.n_specular,
        "normalization_gain": report.normalization_gain,
        "render_seconds": report.render_seconds,
    }


def _level_sentence(report: TrialReport) -> str:
    level = report.echo_band_level_db
    where = (
        f"the click as heard {report.click_reference_distance_m * 100.0:.0f} "
        "centimetres from the mouth"
    )
    word = "quieter" if level <= 0.0 else "louder"
    return f"In the click band the echo is {abs(level):.1f} decibels {word} than {where}."


def format_trial_text(report: TrialReport, path: object, budget_s: float | None = None) -> str:
    """Describe a trial in plain sentences, one fact per line, for screen readers."""
    lines = [
        f"Rendered one trial to {path}.",
        (
            f"The disc is {report.disc_diameter_m * 100.0:.1f} centimetres across, "
            f"{report.disc_distance_m * 100.0:.0f} centimetres in front of you."
        ),
        f"Its echo arrives {report.echo_delay_s * 1000.0:.1f} milliseconds after the click.",
        (
            f"That delay means the echo came from {report.echo_distance_m * 100.0:.0f} "
            "centimetres away."
        ),
        _level_sentence(report),
        (
            f"Compared with a wall at the same distance, the echo is "
            f"{abs(report.echo_ratio_db):.1f} decibels "
            f"{'louder' if report.echo_ratio_db > 0 else 'quieter'}."
        ),
        (
            f"The engine used {report.n_arrivals} arrivals, of which "
            f"{report.n_specular} {'is' if report.n_specular == 1 else 'are'} the mirror "
            "reflection."
        ),
    ]
    if budget_s is not None:
        lines.append(
            f"Rendering took {report.render_seconds:.1f} seconds; the budget is "
            f"{budget_s:.0f} seconds."
        )
    return "\n".join(lines) + "\n"
