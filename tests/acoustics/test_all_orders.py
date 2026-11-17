# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Candidate C2 (edge diffraction of all orders) must agree with C1 where they overlap,
converge, and obey the same physics."""

from __future__ import annotations

import numpy as np
import pytest

from soundsight.acoustics import canonical as cn
from soundsight.acoustics import engine as eg
from soundsight.acoustics.candidates import all_orders as ao
from soundsight.acoustics.candidates import second_order as so

SMALL_DISC = eg.Plate.regular(0.0255, 48, centre=(0, 0, 0.33))


def test_truncated_after_two_orders_it_reproduces_c1() -> None:
    """The two candidates share no quadrature; their second orders must agree."""
    f = np.array([2000.0, 3000.0, 4000.0])
    d, a = so.second_order_arrivals(SMALL_DISC, (0, 0, 0), (0, 0, 0), 8000)
    c1 = eg.Arrivals(d, a, ()).frequency_response(f)
    kernel = ao.build_kernel(SMALL_DISC, (0, 0, 0), (0, 0, 0), 4000)
    c2 = np.array([ao.higher_order_response(kernel, fi, max_order=2) for fi in f])
    assert np.abs(c2 - c1).max() < 1e-3 * np.abs(c1).max()


def test_series_of_orders_converges_to_the_solution() -> None:
    kernel = ao.build_kernel(SMALL_DISC, (0, 0, 0), (0, 0, 0), 4000)
    full = ao.higher_order_response(kernel, 3000.0)
    errors = [abs(ao.higher_order_response(kernel, 3000.0, max_order=n) - full) for n in (3, 6, 12)]
    assert errors[0] > errors[1] > errors[2]
    assert errors[2] < 1e-4 * abs(full)


def test_reciprocity_on_an_irregular_plate() -> None:
    plate = eg.Plate(np.array([[-0.2, -0.2, 0], [0.2, -0.2, 0], [0.2, 0.25, 0], [-0.15, 0.2, 0.0]]))
    s, r, f = (0.05, -0.03, 0.4), (-0.1, 0.12, 0.7), np.array([700.0, 2500.0])
    a = ao.echo_all_orders(plate, s, r, f)
    b = ao.echo_all_orders(plate, r, s, f)
    np.testing.assert_allclose(a, b, rtol=1e-8)


def test_polygon_and_quadrature_converge() -> None:
    f = np.array([2000.0, 3000.0])

    def echo(n_sides: int, interval: float) -> np.ndarray:
        old = ao.INTERVAL_PER_WAVELENGTH
        ao.INTERVAL_PER_WAVELENGTH = interval
        try:
            plate = eg.Plate.regular(0.05, n_sides, centre=(0, 0, 0.5))
            return ao.echo_all_orders(plate, (0, 0, 0), None, f)
        finally:
            ao.INTERVAL_PER_WAVELENGTH = old

    fine = echo(96, 0.5)
    assert np.abs(echo(48, 0.5) - fine).max() < 1e-3 * np.abs(fine).max()
    assert np.abs(echo(24, 0.5) - fine).max() > np.abs(echo(48, 0.5) - fine).max()
    # More points per edge than the default changes the result very little.
    denser = echo(24, 0.0625)
    assert np.abs(denser - echo(24, 0.5)).max() < 2e-3 * np.abs(denser).max()


def test_impulse_response_matches_the_spectrum() -> None:
    fs, n = 8000, 512
    disc = eg.Plate.regular(0.03, 24, centre=(0, 0, 1.0))
    ir = ao.impulse_response(disc, (0, 0, 0), None, fs, n)
    f = np.fft.rfftfreq(n, 1 / fs)
    pick = np.flatnonzero((f > 100) & (f < 0.4 * fs))[::12]
    exact = ao.echo_all_orders(disc, (0, 0, 0), None, f[pick])
    assert np.abs(np.fft.rfft(ir)[pick] - exact).max() < 1e-4 * np.abs(exact).max()


def test_budget_stops_the_impulse_response() -> None:
    disc = eg.Plate.regular(0.03, 24, centre=(0, 0, 1.0))
    with pytest.raises(ao.BudgetExceededError, match="stopped after") as info:
        ao.impulse_response(disc, (0, 0, 0), None, 8000, 512, budget_s=0.0)
    assert info.value.done == 0
    assert info.value.total > 0


def test_model_wraps_canonical_targets() -> None:
    model = ao.AllOrdersPlateModel()
    assert isinstance(model, cn.EchoModel)
    np.testing.assert_array_equal(model.echo_ratio(cn.Wall(1.0), [1000.0]), [1.0])
    with pytest.raises(cn.UnsupportedTargetError):
        model.echo_ratio(cn.Sphere(0.1, 1.0), [1000.0])
    assert np.isfinite(model.echo_ratio(cn.Disk(0.05, 0.5), [3000.0])).all()


@pytest.mark.parametrize(
    "source",
    [(0.6, 0.0, 0.01), (0.2, 0.5, 0.0)],  # near the plane beyond an edge; on an edge line
)
def test_refuses_geometry_outside_its_validity(source: tuple[float, ...]) -> None:
    square = eg.Plate(np.array([[-0.2, -0.2, 0], [0.2, -0.2, 0], [0.2, 0.2, 0], [-0.2, 0.2, 0.0]]))
    with pytest.raises(eg.GeometryError, match="edge"):
        ao.build_kernel(square, source, source, 2000.0)


def test_invalid_order_and_frequency() -> None:
    kernel = ao.build_kernel(SMALL_DISC, (0, 0, 0), (0, 0, 0), 4000)
    with pytest.raises(ValueError, match="max_order"):
        ao.higher_order_response(kernel, 3000.0, max_order=1)
    with pytest.raises(ValueError, match="f_max"):
        ao.edge_nodes(SMALL_DISC, 0.0)
