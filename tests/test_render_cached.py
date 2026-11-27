# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Candidate R3 of EXP-0006: trials rendered from a per-disc echo cache."""

from __future__ import annotations

import time

import numpy as np
import pytest

from soundsight.acoustics import engine as eg
from soundsight.acoustics.candidates import all_orders as ao
from soundsight.click.synth import synth_click
from soundsight.exercise import render_all_orders as r2
from soundsight.exercise import render_cached as r3

FS = 16_000  # keeps the tests fast; arrivals still clear the rendering filter


@pytest.fixture(scope="module")
def cache() -> r3.DiscEchoCache:
    return r3.build_cache(0.051, 0.66, FS)


def test_grid_starts_at_zero_and_follows_the_window() -> None:
    f = r3.cache_grid(FS)
    assert f[0] == 0.0
    assert np.allclose(np.diff(f), 1.0 / r3.WINDOW_S)
    assert f[-1] <= r2.PASSBAND * FS


def test_higher_orders_are_placed_at_the_mirror_echo(cache: r3.DiscEchoCache) -> None:
    ir = r3.cached_impulse_response(cache)
    first = r2.first_order_impulse_response(0.051, 0.66, FS)
    start = cache.onset_samples
    assert start == int(2 * 0.66 / 343 * FS)
    np.testing.assert_array_equal(ir[:start], first[:start])  # nothing added before it


def test_r3_carries_the_all_orders_echo(cache: r3.DiscEchoCache) -> None:
    """Weighted by the click's spectrum, R3 must match diffraction of all orders."""
    click = synth_click(FS)
    ir = r3.cached_impulse_response(cache)
    f = np.geomspace(300.0, 0.4 * FS, 40)
    plate48 = eg.Plate.regular(0.0255, r2.ALL_ORDERS_SIDES, centre=(0, 0, 0.66))
    reference = ao.frequency_response(plate48, (0, 0, 0), None, f)
    weight = np.abs(r2.dtft(click, FS, f)) ** 2
    got = r2.dtft(ir, FS, f)
    error = np.sum(weight * np.abs(reference - got) ** 2) / np.sum(weight * np.abs(reference) ** 2)
    assert error < 10 ** (-3.0)  # better than -30 dB


def test_build_is_resumable() -> None:
    store: dict[float, complex] = {}
    with pytest.raises(ao.BudgetExceededError):
        r3.build_cache(0.051, 0.66, FS, store=store, deadline=time.perf_counter() - 1.0)
    built = r3.build_cache(0.051, 0.66, FS, store=store)
    assert set(store) == {float(x) for x in r3.cache_grid(FS)}
    assert built.higher.size == r3.cache_grid(FS).size


def test_render_trial_from_cache(cache: r3.DiscEchoCache) -> None:
    recording, report = r3.render_trial_from_cache(cache, click_reference_distance_m=0.5)
    assert np.max(np.abs(recording.samples)) == pytest.approx(0.95)
    assert report.echo_delay_s == pytest.approx(2 * 0.66 / 343, abs=3 / FS)
    assert report.echo_ratio_db < -20.0
    with pytest.raises(ValueError, match="click_reference_distance_m"):
        r3.render_trial_from_cache(cache, click_reference_distance_m=0.0)
    with pytest.raises(ValueError, match="either"):
        r3.render_trial_from_cache(
            cache,
            click_reference_distance_m=0.5,
            click=np.ones(5),
            click_params=object(),  # type: ignore[arg-type]
        )
