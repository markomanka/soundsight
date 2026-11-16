# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""The closed-form solutions must satisfy the limits every acoustics textbook gives."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from scipy import special

from soundsight.acoustics.reference import analytic as an

C = an.SPEED_OF_SOUND


def _f(ka: float | np.ndarray, a: float) -> np.ndarray:
    return np.atleast_1d(ka) * C / (2 * np.pi * a)


@pytest.mark.parametrize("bad", [[0.0], [-1.0], [np.nan], [np.inf]])
def test_frequencies_must_be_positive_and_finite(bad: list[float]) -> None:
    with pytest.raises(ValueError, match="strictly positive"):
        an.wavenumber(bad)


def test_speed_of_sound_must_be_positive() -> None:
    with pytest.raises(ValueError, match="speed of sound"):
        an.wavenumber([100.0], c=0.0)


@pytest.mark.parametrize(
    "call",
    [
        lambda: an.free_field([100.0], 0.0),
        lambda: an.disk_echo_ratio_kirchhoff([100.0], 0.0, 1.0),
        lambda: an.disk_echo_ratio_kirchhoff([100.0], 1.0, -1.0),
        lambda: an.disk_echo_ratio_edge_diffraction([100.0], -1.0, 1.0),
        lambda: an.disk_echo_ratio_edge_diffraction([100.0], 1.0, 0.0),
        lambda: an.compact_disk_echo_ratio([100.0], 0.0, 1.0),
        lambda: an.compact_disk_echo_ratio([100.0], 1.0, 0.0),
        lambda: an.sphere_echo([100.0], 0.0, 1.0),
        lambda: an.compact_sphere_echo_ratio([100.0], -1.0, 1.0),
    ],
)
def test_lengths_must_be_positive(call) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="must be positive"):
        call()


@pytest.mark.parametrize("fn", [an.sphere_echo, an.compact_sphere_echo_ratio])
def test_listener_must_be_outside_sphere(fn) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="outside the sphere"):
        fn([100.0], 1.0, 0.5)


def test_free_field_spreading_and_delay() -> None:
    f = np.array([500.0, 2000.0])
    h = an.free_field(f, 2.0)
    np.testing.assert_allclose(np.abs(h), 0.5)
    np.testing.assert_allclose(np.angle(h * np.exp(2j * np.pi * f * 2.0 / C)), 0.0, atol=1e-9)


def test_wall_is_a_mirror() -> None:
    f = np.array([300.0, 3000.0])
    np.testing.assert_allclose(an.plane_echo(f, 0.7), an.free_field(f, 1.4))


def test_sphere_matches_rayleigh_far_field_limit() -> None:
    # |p_s| -> (5/6) k^2 a^3 / r^2 for ka << 1 and kr >> 1 (Rayleigh, 1872).
    a, r = 0.01, 10.0
    for f in (50.0, 100.0, 200.0):
        k = 2 * np.pi * f / C
        exact = abs(an.sphere_echo([f], a, r)[0])
        assert exact == pytest.approx((5 / 6) * k**2 * a**3 / r**2, rel=3e-3)


@pytest.mark.parametrize("kr", [0.5, 1.0, 2.0, 5.0, 20.0])
def test_compact_sphere_matches_exact_series_at_any_distance(kr: float) -> None:
    r = 0.5
    k = kr / r
    a = 0.02 / k
    f = [k * C / (2 * np.pi)]
    exact = an.sphere_echo_ratio(f, a, r)[0]
    approx = an.compact_sphere_echo_ratio(f, a, r)[0]
    assert abs(exact / approx) == pytest.approx(1.0, abs=3e-3)
    assert np.angle(exact / approx) == pytest.approx(0.0, abs=3e-3)


def test_sphere_tends_to_geometrical_reflection() -> None:
    # A convex mirror of radius a seen from distance r reflects a/r of a flat wall.
    a, r = 0.3, 1.3
    ratio = np.abs(an.sphere_echo_ratio(_f(np.linspace(40, 80, 200), a), a, r))
    assert ratio.mean() == pytest.approx(a / r, rel=3e-3)
    assert np.ptp(ratio) < 0.01 * a / r


def test_sphere_series_refuses_a_listener_touching_the_surface() -> None:
    with pytest.raises(ArithmeticError, match="too close to the surface"):
        an.sphere_echo([20000.0], 1.0, 1.0 + 1e-9)


@pytest.mark.parametrize("x", [0.03, 1.0, 3.14159, 4.4934, 12.0, 60.0])
def test_scaled_bessel_recurrences_match_scipy(x: float) -> None:
    n = np.arange(0, 31)
    np.testing.assert_allclose(
        np.exp(an._log_bessel_j(30, x)).real, special.spherical_jn(n, x), rtol=1e-9, atol=1e-300
    )
    hankel = special.spherical_jn(n, x) - 1j * special.spherical_yn(n, x)
    np.testing.assert_allclose(np.exp(an._log_hankel2(30, x)), hankel, rtol=1e-9)


@pytest.mark.parametrize("x", [0.2, 1.0, 3.0])
def test_scaled_recurrences_at_orders_where_plain_functions_overflow(x: float) -> None:
    """At order 400 y_n is about 1e800: check the logarithms against the known asymptotics."""
    n = 400
    log_double_factorial = special.gammaln(2 * n + 2) - n * np.log(2) - special.gammaln(n + 1)
    log_j = n * np.log(x) - log_double_factorial + np.log1p(-(x**2) / (2 * (2 * n + 3)))
    log_y = (
        log_double_factorial - np.log(2 * n + 1) - (n + 1) * np.log(x)
        + np.log1p(x**2 / (2 * (2 * n - 1)))
    )  # fmt: skip
    assert an._log_bessel_j(n, x)[n].real == pytest.approx(log_j, abs=1e-4)
    hankel = an._log_hankel2(n, x)[n]
    assert hankel.real == pytest.approx(log_y, abs=1e-4)  # |h| = |y| when j is negligible
    assert log_y > 700  # beyond the largest double: the plain function would be infinite


def test_sphere_series_is_stable_where_it_needs_hundreds_of_terms() -> None:
    f = [C / (2 * np.pi * 3.0)]  # ka = 1, listener a twelfth of a radius from the surface
    loose = an.sphere_echo(f, 3.0, 3.25, tolerance=1e-6)[0]
    tight = an.sphere_echo(f, 3.0, 3.25, tolerance=1e-12)[0]
    assert np.isfinite(tight)
    assert abs(loose / tight - 1) < 1e-5


def test_kirchhoff_disk_limits() -> None:
    f = _f(np.linspace(1, 30, 100), 1.0)
    # A vanishing disk gives no echo; an enormous one is a wall.
    assert np.abs(an.disk_echo_ratio_kirchhoff(f, 1e-6, 1.0)).max() < 1e-6
    far_rim = an.disk_echo_ratio_kirchhoff(f, 1e4, 1.0)
    np.testing.assert_allclose(np.abs(far_rim), 1.0, atol=1e-7)
    # The rim wave can at most double the mirror echo (one full Fresnel zone).
    assert np.abs(an.disk_echo_ratio_kirchhoff(f, 0.3, 1.0)).max() <= 1 + 1 / 1.09 + 1e-12


def test_edge_diffraction_reduces_to_kirchhoff_for_distant_disks() -> None:
    # Seen from far away the listener is in the mirror direction of the rim: cot -> 1.
    f = _f(np.linspace(5, 50, 50), 1.0)
    np.testing.assert_allclose(
        an.disk_echo_ratio_edge_diffraction(f, 1.0, 1e4),
        an.disk_echo_ratio_kirchhoff(f, 1.0, 1e4),
        rtol=0,
        atol=2e-4,  # the echo ratio passes through zero, so compare absolutely
    )


def test_edge_coefficient_is_larger_than_kirchhoff_up_close() -> None:
    f = _f(np.linspace(5, 50, 400), 0.3)
    edge = np.abs(an.disk_echo_ratio_edge_diffraction(f, 0.3, 1.0)).max()
    kirchhoff = np.abs(an.disk_echo_ratio_kirchhoff(f, 0.3, 1.0)).max()
    assert edge > 1.1 * kirchhoff


def test_compact_disk_scales_with_radius_cubed_and_frequency_squared() -> None:
    base = abs(an.compact_disk_echo_ratio([100.0], 0.01, 100.0)[0])
    assert abs(an.compact_disk_echo_ratio([100.0], 0.02, 100.0)[0]) == pytest.approx(8 * base)
    assert abs(an.compact_disk_echo_ratio([200.0], 0.01, 100.0)[0]) == pytest.approx(
        4 * base, rel=1e-3
    )


positive = st.floats(0.05, 5.0)


@given(a=positive, extra=positive, ka=st.floats(0.05, 30.0), scale=st.floats(0.01, 100.0))
def test_everything_depends_only_on_sizes_in_wavelengths(
    a: float, extra: float, ka: float, scale: float
) -> None:
    """Linear acoustics is scale-invariant: the reason cheap tests still bind at 3 kHz."""
    d = a + extra
    f, fs = _f(ka, a), _f(ka, a * scale)
    for fn in (
        an.disk_echo_ratio_kirchhoff,
        an.disk_echo_ratio_edge_diffraction,
        an.compact_disk_echo_ratio,
        an.sphere_echo_ratio,
        an.compact_sphere_echo_ratio,
    ):
        np.testing.assert_allclose(fn(fs, a * scale, d * scale), fn(f, a, d), rtol=1e-7)
