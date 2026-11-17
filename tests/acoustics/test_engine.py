# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""The production engine must obey the physics that holds for every scene, not only for
the canonical targets: continuity at reflection boundaries, reciprocity, scale
invariance, the wall limit, convergence, and a faithful impulse response."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from soundsight.acoustics import engine as eg
from soundsight.acoustics.reference import analytic as an

C = an.SPEED_OF_SOUND
SQUARE = eg.Plate(np.array([[-0.2, -0.2, 0], [0.2, -0.2, 0], [0.2, 0.2, 0], [-0.2, 0.2, 0.0]]))


# ---------------------------------------------------------------- plate geometry
@pytest.mark.parametrize(
    ("vertices", "message"),
    [
        ([[0, 0, 0], [1, 0, 0]], "at least 3"),
        ([[0, 0, 0], [1, 0, 0], [np.nan, 1, 0]], "finite"),
        ([[0, 0, 0], [0, 0, 0], [0, 0, 0]], "degenerate"),
        ([[0, 0, 0], [1, 0, 0], [2, 0, 0]], "zero area"),
        ([[0, 0, 0], [1, 0, 0], [1, 1, 0.1], [0, 1, 0]], "coplanar"),
        ([[0, 0, 0], [1, 0, 0], [1, 0, 0], [0, 1, 0]], "repeated"),
        ([[0, 0, 0], [2, 0, 0], [1, 0.2, 0], [2, 2, 0], [0, 2, 0]], "convex"),
    ],
)
def test_invalid_plates_are_rejected(vertices: list[list[float]], message: str) -> None:
    with pytest.raises(eg.GeometryError, match=message):
        eg.Plate(np.asarray(vertices, dtype=float))


def test_regular_polygon_has_the_area_of_the_disk() -> None:
    plate = eg.Plate.regular(0.1, 12, centre=(1, 2, 3), normal=(1, 1, 0))
    v = plate.vertices - plate.vertices.mean(axis=0)
    area = 0.5 * np.linalg.norm(np.cross(v, np.roll(v, -1, axis=0)).sum(axis=0))
    assert area == pytest.approx(np.pi * 0.1**2)
    assert plate.vertices.mean(axis=0) == pytest.approx([1, 2, 3])
    assert abs(plate.normal @ np.array([1, 1, 0]) / np.sqrt(2)) == pytest.approx(1.0)
    vertex = eg.Plate.regular(0.1, 12, equal_area=False)
    assert np.linalg.norm(vertex.vertices, axis=1) == pytest.approx(0.1)


@pytest.mark.parametrize(("radius", "sides"), [(0.0, 8), (0.1, 2)])
def test_invalid_regular_polygons(radius: float, sides: int) -> None:
    with pytest.raises(eg.GeometryError):
        eg.Plate.regular(radius, sides)


def test_vertex_order_does_not_matter() -> None:
    reverse = eg.Plate(SQUARE.vertices[::-1])
    f = [1000.0, 3000.0]
    a = eg.plate_echo(SQUARE, (0.05, 0.02, 0.6), f_max=3000).frequency_response(f)
    b = eg.plate_echo(reverse, (0.05, 0.02, 0.6), f_max=3000).frequency_response(f)
    np.testing.assert_allclose(a, b, rtol=1e-12)


# ---------------------------------------------------------------- specular reflection
def test_specular_reflection_follows_the_image_source() -> None:
    s, r = np.array([0.05, 0.0, 0.5]), np.array([-0.05, 0.1, 0.8])
    delay, amplitude = eg.specular_arrival(SQUARE, s, r)  # type: ignore[misc]
    path = np.linalg.norm(r - s * np.array([1, 1, -1]))
    assert delay == pytest.approx(path / C)
    assert amplitude == pytest.approx(1 / path)


def test_both_faces_reflect() -> None:
    assert eg.specular_arrival(SQUARE, (0, 0, -0.5), (0, 0, -0.5)) is not None


@pytest.mark.parametrize(
    ("source", "receiver"),
    [
        ((0.0, 0.0, 0.5), (0.0, 0.0, -0.5)),  # opposite sides
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.5)),  # in the plane
        ((1.0, 0.0, 0.5), (1.0, 0.0, 0.5)),  # reflection point off the plate
    ],
)
def test_no_specular_reflection(source: tuple[float, ...], receiver: tuple[float, ...]) -> None:
    assert eg.specular_arrival(SQUARE, source, receiver) is None


def test_reflection_point_on_an_edge_counts_half() -> None:
    _, on_edge = eg.specular_arrival(SQUARE, (0.2, 0.0, 0.5), (0.2, 0.0, 0.5))  # type: ignore[misc]
    _, inside = eg.specular_arrival(SQUARE, (0.1, 0.0, 0.5), (0.1, 0.0, 0.5))  # type: ignore[misc]
    assert on_edge == pytest.approx(0.5 * inside)


# ---------------------------------------------------------------- reflection boundary
@pytest.mark.parametrize("eps", [1e-3, 1e-5, 1e-7])
def test_field_is_continuous_where_the_reflection_point_crosses_an_edge(eps: float) -> None:
    """The specular echo (amplitude 0.77 here) switches off at the boundary; the
    diffracted field must replace it exactly. This fixes the sign and the strength of
    the diffraction term and tests the quadrature near the apex."""
    source, f = np.array([0.0, 0.05, 0.5]), np.array([500.0, 2000.0, 6000.0])
    boundary = 0.2 * 1.2 / 0.5  # receiver x at which the reflection point is on x = 0.2

    def h(x: float) -> np.ndarray:
        return eg.plate_echo(SQUARE, source, (x, 0.05, 0.7), f_max=8000).frequency_response(f)

    left, on, right = h(boundary - eps), h(boundary), h(boundary + eps)
    assert eg.specular_arrival(SQUARE, source, (boundary - eps, 0.05, 0.7)) is not None
    assert eg.specular_arrival(SQUARE, source, (boundary + eps, 0.05, 0.7)) is None
    assert np.max(np.abs(left - right)) < 30 * eps  # smooth: the step is slope x distance
    assert np.max(np.abs(on - 0.5 * (left + right))) < 1e-9 + 200 * eps**2


# ---------------------------------------------------------------- physical laws
positions = st.tuples(st.floats(-0.5, 0.5), st.floats(-0.5, 0.5), st.floats(0.15, 1.5))


@given(source=positions, receiver=positions)
def test_reciprocity(source: tuple[float, ...], receiver: tuple[float, ...]) -> None:
    f = [700.0, 2500.0, 5000.0]
    a = eg.plate_echo(SQUARE, source, receiver, f_max=5000).frequency_response(f)
    b = eg.plate_echo(SQUARE, receiver, source, f_max=5000).frequency_response(f)
    np.testing.assert_allclose(a, b, rtol=1e-9, atol=1e-12)


@given(scale=st.floats(0.05, 20.0), source=positions)
def test_only_sizes_in_wavelengths_matter(scale: float, source: tuple[float, ...]) -> None:
    """Scaling the scene by s and frequency by 1/s scales the echo by 1/s (spreading)."""
    f = np.array([800.0, 3000.0])
    a = eg.plate_echo(SQUARE, source, f_max=3000).frequency_response(f)
    big = eg.Plate(SQUARE.vertices * scale)
    b = eg.plate_echo(big, np.asarray(source) * scale, f_max=3000 / scale).frequency_response(
        f / scale
    )
    np.testing.assert_allclose(b * scale, a, rtol=1e-8, atol=1e-12)


def test_large_plate_echoes_like_a_wall() -> None:
    f = np.linspace(2000.0, 4000.0, 40)
    deviation = []
    for half_side in (1.0, 4.0, 16.0):
        corners = np.array([[-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0]]) * half_side
        plate = eg.Plate(corners + np.array([0.0, 0.0, 1.0]))  # 1 m in front
        echo = eg.plate_echo(plate, (0, 0, 0), f_max=4000).frequency_response(f)
        deviation.append(float(np.max(np.abs(echo / an.plane_echo(f, 1.0) - 1))))
    assert deviation[0] > deviation[1] > deviation[2]
    assert deviation[2] < 0.01


def test_quadrature_is_converged() -> None:
    f = [1000.0, 4000.0]
    a = eg.plate_echo(SQUARE, (0.07, -0.03, 0.4), (0.0, 0.1, 0.9), f_max=4000)
    b = eg.plate_echo(SQUARE, (0.07, -0.03, 0.4), (0.0, 0.1, 0.9), f_max=8000)
    np.testing.assert_allclose(a.frequency_response(f), b.frequency_response(f), rtol=1e-9)


def test_disk_polygons_converge_at_second_order() -> None:
    f = np.linspace(2000.0, 4000.0, 20)

    def echo(n: int) -> np.ndarray:
        plate = eg.Plate.regular(0.05, n, centre=(0, 0, 1.0))
        return eg.plate_echo(plate, (0, 0, 0), f_max=4000).frequency_response(f)

    reference = echo(512)
    errors = [float(np.max(np.abs(echo(n) - reference))) for n in (24, 48, 96)]
    assert errors[0] / errors[1] == pytest.approx(4.0, rel=0.15)
    assert errors[1] / errors[2] == pytest.approx(4.0, rel=0.15)


# ---------------------------------------------------------------- impulse response
def test_rendered_impulse_response_matches_the_frequency_response() -> None:
    fs, n = 48000, 4096
    arrivals = eg.plate_echo(
        eg.Plate.regular(0.0875, 96, centre=(0, 0, 1.0)), (0, 0, 0), f_max=fs / 2
    )
    ir = eg.render(arrivals, fs, n)
    f = np.fft.rfftfreq(n, 1 / fs)
    band = (f > 50) & (f < 0.45 * fs)
    exact = arrivals.frequency_response(f[band])
    assert np.max(np.abs(np.fft.rfft(ir)[band] - exact)) < 2e-4 * np.max(np.abs(exact))
    # Nothing before the first arrival, beyond the fractional-delay filter's half-width.
    first = int(np.flatnonzero(np.abs(ir) > 1e-6 * np.abs(ir).max())[0])
    assert first >= int(2.0 / C * fs) - 32


def test_render_validates_its_arguments() -> None:
    arrivals = eg.Arrivals(np.array([0.001]), np.array([1.0]), ())
    with pytest.raises(ValueError, match="positive"):
        eg.render(arrivals, 0, 10)
    assert eg.render(arrivals, 48000, 10).shape == (10,)  # arrival beyond the end: silent


def test_frequency_response_in_chunks_equals_direct_sum() -> None:
    arrivals = eg.plate_echo(SQUARE, (0.0, 0.0, 0.5), f_max=8000)
    f = np.linspace(100.0, 8000.0, 400)  # more frequencies than one chunk holds
    direct = np.exp(-2j * np.pi * np.outer(f, arrivals.delays)) @ arrivals.amplitudes
    np.testing.assert_allclose(arrivals.frequency_response(f), direct, rtol=1e-10)


# ---------------------------------------------------------------- input checks
@pytest.mark.parametrize(
    ("call", "error", "message"),
    [
        (lambda: eg.plate_echo(SQUARE, (0, 0, 1, 2), f_max=1000), eg.GeometryError, "3-vector"),
        (lambda: eg.plate_echo(SQUARE, (0.2, 0.5, 0.0), f_max=1000), eg.GeometryError, "edge"),
        (lambda: eg.diffraction_arrivals(SQUARE, (0, 0, 1), (0, 0, 1), 0.0), ValueError, "f_max"),
    ],
)
def test_invalid_inputs(call, error: type[Exception], message: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(error, match=message):
        call()
