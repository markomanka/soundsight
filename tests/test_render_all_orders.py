# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Candidate R2 of EXP-0005, and the banded all-orders solving it relies on."""

from __future__ import annotations

import time

import numpy as np
import pytest

from soundsight.acoustics import engine as eg
from soundsight.acoustics.candidates import all_orders as ao
from soundsight.click.synth import synth_click
from soundsight.exercise import render_all_orders as r2

FS = 16_000  # low enough to keep the test fast; arrivals still clear the filter


def test_banded_solving_matches_a_single_kernel() -> None:
    plate = eg.Plate.regular(0.03, 24, centre=(0, 0, 0.5))
    f = np.array([600.0, 1500.0, 3200.0])
    banded = ao.frequency_response(plate, (0, 0, 0), None, f)
    single = ao.echo_all_orders(plate, (0, 0, 0), None, f)
    assert np.abs(banded - single).max() < 1e-3 * np.abs(single).max()


def test_cache_is_reused_and_deadline_keeps_progress() -> None:
    plate = eg.Plate.regular(0.03, 24, centre=(0, 0, 0.5))
    f = np.array([700.0, 1400.0])
    cache: dict[float, complex] = {}
    with pytest.raises(ao.BudgetExceededError):
        ao.higher_order_responses(
            plate, (0, 0, 0), None, f, cache=cache, deadline=time.perf_counter() - 1.0
        )
    first = ao.higher_order_responses(plate, (0, 0, 0), None, f, cache=cache)
    assert set(cache) == {700.0, 1400.0}
    cache[700.0] = 123.0 + 0j  # a cached value is used as it stands
    again = ao.higher_order_responses(plate, (0, 0, 0), None, f, cache=cache)
    assert again[0] == 123.0
    assert again[1] == first[1]


def test_solved_bins_follow_the_click_and_the_passband() -> None:
    click = synth_click(FS)
    bins = r2.solved_bins(click, 512, FS)
    f = np.fft.rfftfreq(512, 1 / FS)[bins]
    assert f.min() > 0
    assert f.max() <= r2.PASSBAND * FS
    power = np.abs(np.fft.rfft(click, 512)) ** 2
    assert power[bins].min() >= power.max() * 1e-6


def test_r2_carries_the_all_orders_echo_where_the_click_has_energy() -> None:
    d, dist = 0.051, 0.66
    click = synth_click(FS)
    ir2 = r2.all_orders_impulse_response(d, dist, click, FS)
    ir1 = r2.first_order_impulse_response(d, dist, FS)
    bins = r2.solved_bins(click, ir2.size, FS)
    f = np.fft.rfftfreq(ir2.size, 1 / FS)[bins]
    plate48 = eg.Plate.regular(d / 2, r2.ALL_ORDERS_SIDES, centre=(0, 0, dist))
    reference = ao.frequency_response(plate48, (0, 0, 0), None, f)
    weight = np.abs(np.fft.rfft(click, ir2.size)[bins]) ** 2
    for ir, bound in ((ir2, 1e-3), (ir1, None)):
        got = np.fft.rfft(ir, ir2.size)[bins]  # R1's response is shorter: pad it
        error = np.sum(weight * np.abs(reference - got) ** 2) / np.sum(
            weight * np.abs(reference) ** 2
        )
        if bound is not None:
            assert error < bound  # R2: within -30 dB of the all-orders echo
        else:
            assert error > 1e-2  # R1 misses it for this small disc


def test_render_trial_all_orders() -> None:
    recording, report = r2.render_disc_trial_all_orders(
        0.051, 0.66, click_reference_distance_m=0.5, sample_rate=FS
    )
    assert np.max(np.abs(recording.samples)) == pytest.approx(0.95)
    assert report.echo_delay_s == pytest.approx(2 * 0.66 / 343, abs=3 / FS)
    assert report.echo_ratio_db < -20.0
    with pytest.raises(ValueError, match="click_reference_distance_m"):
        r2.render_disc_trial_all_orders(0.051, 0.66, click_reference_distance_m=0.0)
    with pytest.raises(ValueError, match="either"):
        r2.render_disc_trial_all_orders(
            0.051,
            0.66,
            click_reference_distance_m=0.5,
            click=np.ones(5),
            click_params=object(),  # type: ignore[arg-type]
        )


def test_dtft_matches_fft_at_bins() -> None:
    x = np.random.default_rng(0).normal(size=64)
    f = np.fft.rfftfreq(64, 1 / FS)
    np.testing.assert_allclose(r2.dtft(x, FS, f), np.fft.rfft(x), atol=1e-9)


def test_banded_solving_includes_zero_frequency() -> None:
    """Zero frequency is a valid request (R3 of EXP-0006 needs it) and must be solved."""
    plate = eg.Plate.regular(0.03, 24, centre=(0, 0, 0.5))
    values = ao.higher_order_responses(plate, (0, 0, 0), None, np.array([0.0, 800.0]))
    assert np.isfinite(values).all()
    kernel = ao.build_kernel(plate, (0, 0, 0), (0, 0, 0), 800.0)
    assert values[0] == pytest.approx(ao.higher_order_response(kernel, 0.0), rel=1e-9)
