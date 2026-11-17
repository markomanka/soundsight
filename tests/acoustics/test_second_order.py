# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Candidate C1 (second-order edge diffraction) must obey the same physics as the engine.

The decisive test fixes its only free choice, the weight of the second-order term, from
physics alone: second-order diffraction must cancel the jump of first-order diffraction
across the plane of the plate beyond an edge.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from soundsight.acoustics import canonical as cn
from soundsight.acoustics import engine as eg
from soundsight.acoustics.candidates import second_order as so

SQUARE = eg.Plate(np.array([[-0.2, -0.2, 0], [0.2, -0.2, 0], [0.2, 0.2, 0], [-0.2, 0.2, 0.0]]))
GRAZED_EDGE = 1  # the edge x = 0.2


def _h2(
    source: object, receiver: object, f: np.ndarray, edges: tuple[int, ...] | None = None
) -> np.ndarray:
    d, a = so.second_order_arrivals(SQUARE, source, receiver, 8000, receiving_edges=edges)  # type: ignore[arg-type]
    return eg.Arrivals(d, a, ()).frequency_response(f)


def test_second_order_cancels_the_first_order_jump_beyond_an_edge() -> None:
    """Just above and just below the plane of the plate, beyond edge x = 0.2, first-order
    diffraction from the other edges jumps (the plate face blocks one side); the
    second-order paths that graze edge x = 0.2 must cancel that jump exactly. This is
    what fixes WEIGHT = 1, without reference to any echo data. The residual is the
    field's own slope times the distance from the plane, so it must fall linearly."""
    source, f = np.array([0.0, 0.0, 0.5]), np.array([500.0, 1500.0, 3000.0, 6000.0])
    residual = []
    for eps in (1e-3, 1e-4):
        up, down = np.array([0.6, 0.05, eps]), np.array([0.6, 0.05, -eps])
        first = eg.plate_echo(SQUARE, source, up, f_max=8000).frequency_response(f)
        first -= eg.plate_echo(SQUARE, source, down, f_max=8000).frequency_response(f)
        second = _h2(source, up, f, (GRAZED_EDGE,)) - _h2(source, down, f, (GRAZED_EDGE,))
        assert np.abs(first).min() > 0.1  # the jump being cancelled is substantial
        residual.append(float(np.max(np.abs(first + so.WEIGHT * second) / np.abs(first))))
    assert residual[0] < 0.02
    assert residual[1] < 0.15 * residual[0]  # linear: ten times closer, ten times smaller


positions = st.tuples(st.floats(-0.3, 0.3), st.floats(-0.3, 0.3), st.floats(0.2, 1.0))


@settings(max_examples=10, deadline=None)
@given(source=positions, receiver=positions)
def test_reciprocity(source: tuple[float, ...], receiver: tuple[float, ...]) -> None:
    f = np.array([800.0, 3000.0])
    np.testing.assert_allclose(
        _h2(source, receiver, f), _h2(receiver, source, f), rtol=1e-8, atol=1e-12
    )


@settings(max_examples=10, deadline=None)
@given(scale=st.floats(0.1, 10.0))
def test_only_sizes_in_wavelengths_matter(scale: float) -> None:
    f = np.array([800.0, 3000.0])
    source = np.array([0.05, -0.02, 0.4])
    small = eg.Arrivals(*so.second_order_arrivals(SQUARE, source, source, 3000), ())
    big_plate = eg.Plate(SQUARE.vertices * scale)
    big = eg.Arrivals(
        *so.second_order_arrivals(big_plate, source * scale, source * scale, 3000 / scale), ()
    )
    np.testing.assert_allclose(
        big.frequency_response(f / scale) * scale,
        small.frequency_response(f),
        rtol=1e-8,
        atol=1e-14,
    )


def test_quadrature_and_polygon_converge() -> None:
    f = np.linspace(2000.0, 4000.0, 5)

    def h2(n: int, f_max: float) -> np.ndarray:
        disc = eg.Plate.regular(0.0255, n, centre=(0, 0, 0.33))
        return eg.Arrivals(
            *so.second_order_arrivals(disc, (0, 0, 0), (0, 0, 0), f_max), ()
        ).frequency_response(f)

    fine = h2(96, 16000)
    assert np.abs(h2(96, 4000) - fine).max() < 1e-3 * np.abs(fine).max()
    errors = [np.abs(h2(n, 8000) - h2(192, 8000)).max() for n in (48, 96)]
    assert errors[1] < 0.5 * errors[0]
    assert errors[1] < 5e-3 * np.abs(fine).max()


def test_dense_render_matches_the_frequency_response() -> None:
    fs, n = 48000, 2048
    disc = eg.Plate.regular(0.05, 48, centre=(0, 0, 0.5))
    echo = so.plate_echo_second_order(disc, (0, 0, 0), f_max=fs / 2)
    ir = so.render_dense(echo, fs, n)
    f = np.fft.rfftfreq(n, 1 / fs)
    pick = np.unique(np.linspace(5, np.searchsorted(f, 0.45 * fs) - 1, 20).astype(int))
    exact = echo.frequency_response(f[pick])
    assert np.abs(np.fft.rfft(ir)[pick] - exact).max() < 2e-3 * np.abs(exact).max()
    # Leakage ahead of the first arrival, from the low-pass filter, stays below -60 dB.
    first_arrival = int(echo.delays.min() * fs)
    assert np.abs(ir[: first_arrival - 64]).max() < 1e-3 * np.abs(ir).max()


def test_model_wraps_canonical_targets() -> None:
    model = so.SecondOrderPlateModel()
    assert isinstance(model, cn.EchoModel)
    np.testing.assert_array_equal(model.echo_ratio(cn.Wall(1.0), [1000.0]), [1.0])
    with pytest.raises(cn.UnsupportedTargetError):
        model.echo_ratio(cn.Sphere(0.1, 1.0), [1000.0])
    ratio = model.echo_ratio(cn.Disk(0.1, 1.0), [3000.0])
    assert np.isfinite(ratio).all()


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: so.second_order_arrivals(SQUARE, (0, 0, 1), (0, 0, 1), 0.0), "f_max"),
        (lambda: so.render_dense(eg.Arrivals(np.zeros(1), np.ones(1), ()), 0, 10), "positive"),
    ],
)
def test_invalid_inputs(call, message: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match=message):
        call()
