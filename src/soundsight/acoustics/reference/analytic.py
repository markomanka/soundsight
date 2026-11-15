# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
r"""Closed-form solutions of linear acoustics, used as ground truth.

Conventions (used throughout :mod:`soundsight.acoustics`)
---------------------------------------------------------
* Time dependence :math:`e^{+i\omega t}`, matching :func:`numpy.fft.fft`: a delay
  :math:`\tau` multiplies a spectrum by :math:`e^{-i\omega\tau}`.
* A *unit point source* radiates :math:`e^{-ikr}/r` in free field; every transfer
  function here is the pressure produced by such a source.
* *Monostatic* means source and receiver at the same point, the first-order model of
  a person hearing the echo of their own click.
* The *echo ratio* of an object is its monostatic echo divided by the echo of an
  infinite rigid wall at the distance of the object's nearest point. It is
  dimensionless: 1 means "echoes like a wall", 0 means "no echo".

All functions take frequencies in hertz (strictly positive) and lengths in metres.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

ComplexArray = NDArray[np.complex128]

#: Speed of sound in air at about 20 degrees Celsius, in metres per second.
SPEED_OF_SOUND = 343.0


def wavenumber(frequency_hz: ArrayLike, c: float = SPEED_OF_SOUND) -> NDArray[np.float64]:
    r"""Return the wavenumber :math:`k = 2\pi f / c` for strictly positive frequencies."""
    f = np.atleast_1d(np.asarray(frequency_hz, dtype=np.float64))
    if not np.all(np.isfinite(f)) or np.any(f <= 0.0):
        msg = "frequencies must be finite and strictly positive"
        raise ValueError(msg)
    if not c > 0.0:
        msg = f"speed of sound must be positive, got {c}"
        raise ValueError(msg)
    return 2.0 * np.pi * f / c


def _positive(name: str, value: float) -> None:
    if not value > 0.0:
        msg = f"{name} must be positive, got {value}"
        raise ValueError(msg)


def free_field(frequency_hz: ArrayLike, distance: float, c: float = SPEED_OF_SOUND) -> ComplexArray:
    """Pressure of a unit point source at ``distance``: :math:`e^{-ikr}/r`. Exact."""
    _positive("distance", distance)
    k = wavenumber(frequency_hz, c)
    return np.asarray(np.exp(-1j * k * distance) / distance, dtype=np.complex128)


def plane_echo(frequency_hz: ArrayLike, distance: float, c: float = SPEED_OF_SOUND) -> ComplexArray:
    """Monostatic echo of an infinite rigid plane at ``distance``. Exact (image source).

    The plane acts as a mirror: the echo is the free field of an image source at twice
    the distance, :math:`e^{-2ikd}/(2d)`.
    """
    return free_field(frequency_hz, 2.0 * distance, c)


def disk_echo_ratio_kirchhoff(
    frequency_hz: ArrayLike, radius: float, distance: float, c: float = SPEED_OF_SOUND
) -> ComplexArray:
    r"""Echo ratio of a rigid disk facing the listener on its axis. APPROXIMATE.

    Kirchhoff (physical-optics) approximation: the disk surface is assumed to carry the
    pressure an infinite wall would. The surface integral then has the closed form

    .. math::

        E(f) = 1 - \frac{d^2}{R^2}\, e^{-2ik(R - d)}, \qquad R = \sqrt{d^2 + a^2},

    a mirror reflection minus a wave from the rim. It is accurate when the disk is
    large compared with the wavelength and wrong for small disks; the wave solver in
    :mod:`soundsight.acoustics.reference.fdtd` quantifies where (see the validation
    document). It is kept because it shows in one line why echo strength depends on
    object size and frequency, which a purely specular model cannot reproduce.
    """
    _positive("radius", radius)
    _positive("distance", distance)
    k = wavenumber(frequency_hz, c)
    rim = float(np.hypot(distance, radius))
    return np.asarray(
        1.0 - (distance / rim) ** 2 * np.exp(-2j * k * (rim - distance)), dtype=np.complex128
    )


def disk_echo_ratio_edge_diffraction(
    frequency_hz: ArrayLike, radius: float, distance: float, c: float = SPEED_OF_SOUND
) -> ComplexArray:
    r"""Echo ratio of a rigid disk on its axis with the correct rim coefficient. APPROXIMATE.

    The Kirchhoff formula uses the physical-optics diffraction coefficient for the rim.
    For a rigid edge seen from the direction of the source, the exact (Sommerfeld
    half-plane) coefficient is larger by :math:`\cot(\varphi/2)`, where
    :math:`\varphi = \arctan(d/a)` is the elevation of the listener above the plane
    of the disk as seen from the rim:

    .. math::

        E(f) = 1 - \cot(\varphi/2)\,\frac{d^2}{R^2}\, e^{-2ik(R - d)} .

    This is first-order edge diffraction: it omits waves that cross the disk from rim
    to rim, and like all edge-diffraction asymptotics it needs the disk to be a few
    wavelengths across (roughly ``ka >= 5``). It stands in for what a geometric engine
    with edge diffraction computes in this scene.
    """
    _positive("radius", radius)
    _positive("distance", distance)
    k = wavenumber(frequency_hz, c)
    rim = float(np.hypot(distance, radius))
    elevation = float(np.arctan2(distance, radius))
    gain = 1.0 / np.tan(elevation / 2.0)
    return np.asarray(
        1.0 - gain * (distance / rim) ** 2 * np.exp(-2j * k * (rim - distance)),
        dtype=np.complex128,
    )


def compact_disk_echo_ratio(
    frequency_hz: ArrayLike, radius: float, distance: float, c: float = SPEED_OF_SOUND
) -> ComplexArray:
    r"""Echo ratio of a rigid disk much smaller than the wavelength. Exact as ``ka -> 0``.

    A small rigid disk facing the source scatters as a dipole whose strength is set by
    its hydrodynamic added mass, :math:`\tfrac83\rho a^3`. Including the near-field
    terms of both the incident gradient and the re-radiated dipole,

    .. math::

        E(f) = -\frac{4}{3\pi}\,\frac{k^2 a^3}{d}\left(1 + \frac{1}{ikd}\right)^2 .

    Valid for :math:`ka \ll 1` and :math:`a \ll d`; the echo grows with the cube of
    the radius and the square of the frequency.
    """
    _positive("radius", radius)
    _positive("distance", distance)
    k = wavenumber(frequency_hz, c)
    near = (1.0 + 1.0 / (1j * k * distance)) ** 2
    return np.asarray(
        -(4.0 / (3.0 * np.pi)) * k**2 * radius**3 * near / distance, dtype=np.complex128
    )


def compact_sphere_echo_ratio(
    frequency_hz: ArrayLike, radius: float, centre_distance: float, c: float = SPEED_OF_SOUND
) -> ComplexArray:
    r"""Echo ratio of a rigid sphere much smaller than the wavelength. Exact as ``ka -> 0``.

    Monopole (excluded volume) plus dipole (added mass) scattering, with near-field
    terms, relative to a wall at the sphere's nearest point:

    .. math::

        p_s = -k^2 a^3\, \frac{e^{-2ikr}}{r^2}
              \left[\tfrac13 + \tfrac12\left(1 + \frac{1}{ikr}\right)^2\right].
    """
    _positive("radius", radius)
    if not centre_distance > radius:
        msg = "the listener must be outside the sphere (centre_distance > radius)"
        raise ValueError(msg)
    k = wavenumber(frequency_hz, c)
    r = centre_distance
    echo = (
        -(k**2)
        * radius**3
        * np.exp(-2j * k * r)
        / r**2
        * (1.0 / 3.0 + 0.5 * (1.0 + 1.0 / (1j * k * r)) ** 2)
    )
    return np.asarray(echo / plane_echo(frequency_hz, r - radius, c), dtype=np.complex128)


def sphere_echo(
    frequency_hz: ArrayLike,
    radius: float,
    centre_distance: float,
    c: float = SPEED_OF_SOUND,
    *,
    tolerance: float = 1e-10,
) -> ComplexArray:
    r"""Monostatic echo of a rigid sphere. Exact (partial-wave series).

    For a unit point source at distance :math:`r` from the centre of a rigid sphere of
    radius :math:`a`, the scattered pressure back at the source is

    .. math::

        p_s = ik \sum_{n=0}^{\infty} (2n+1)\,
              \frac{j_n'(ka)}{h_n^{(2)\prime}(ka)}\, \left[h_n^{(2)}(kr)\right]^2 .

    The series is summed until its terms fall below ``tolerance`` relative to the sum.
    """
    _positive("radius", radius)
    if not centre_distance > radius:
        msg = "the listener must be outside the sphere (centre_distance > radius)"
        raise ValueError(msg)
    k = wavenumber(frequency_hz, c)
    out = np.empty(k.shape, dtype=np.complex128)
    for index, kk in enumerate(k):
        out[index] = _sphere_series(float(kk), radius, centre_distance, tolerance)
    return out


#: The partial-wave series is refused when it would need more terms than this, which
#: happens only when the listener almost touches the sphere.
_MAX_TERMS = 5000
#: Recurrences are rescaled by this factor whenever values grow past it.
_RESCALE = 1e150
_LOG_RESCALE = float(np.log(_RESCALE))


def _log_hankel2(n_max: int, x: float) -> NDArray[np.complex128]:
    """Complex logarithms of the spherical Hankel functions of the second kind, orders 0..n_max.

    Upward recurrence (stable for this function), rescaled so it never overflows.
    """
    out = np.empty(n_max + 1, dtype=np.complex128)
    phase = np.exp(-1j * x)
    prev, cur = 1j * phase / x, -phase * (x - 1j) / x**2
    shift = 0.0
    out[0] = np.log(prev)
    for n in range(1, n_max + 1):
        out[n] = np.log(cur) + shift
        prev, cur = cur, (2 * n + 1) / x * cur - prev
        if abs(cur) > _RESCALE:
            prev, cur, shift = prev / _RESCALE, cur / _RESCALE, shift + _LOG_RESCALE
    return out


def _log_bessel_j(n_max: int, x: float) -> NDArray[np.complex128]:
    """Complex logarithms of the spherical Bessel functions of the first kind, orders 0..n_max.

    Downward (Miller) recurrence from far above ``n_max``, rescaled, then normalised
    with the closed forms of orders 0 and 1.
    """
    start = n_max + 30 + int(np.ceil(x)) + int(np.ceil(np.sqrt(40.0 * (n_max + x + 1))))
    logs = np.empty(n_max + 1, dtype=np.complex128)
    above, cur = 0.0, 1.0
    shift = 0.0
    for n in range(start, -1, -1):
        if n <= n_max:
            logs[n] = np.log(complex(cur)) + shift
        if n == 1:
            cur_one, shift_one = cur, shift
        if n > 0:
            above, cur = cur, (2 * n + 1) / x * cur - above
            if abs(cur) > _RESCALE:
                above, cur, shift = above / _RESCALE, cur / _RESCALE, shift + _LOG_RESCALE
    j0 = np.sin(x) / x
    j1 = np.sin(x) / x**2 - np.cos(x) / x
    # Normalise with whichever of the two is not near a zero.
    if abs(j0) >= abs(j1):
        correction = np.log(complex(j0)) - (np.log(complex(cur)) + shift)
    else:
        correction = np.log(complex(j1)) - (np.log(complex(cur_one)) + shift_one)
    return np.asarray(logs + correction)


def _log_derivative(log_f: NDArray[np.complex128], x: float) -> NDArray[np.complex128]:
    """Logarithms of the derivatives, from f_n' = f_(n-1) - (n+1)/x f_n (orders 1..)."""
    n = np.arange(1, log_f.size)
    ratio = np.exp(log_f[:-1] - log_f[1:])  # f_(n-1)/f_n: adjacent orders, never extreme
    return np.asarray(log_f[1:] + np.log(ratio - (n + 1) / x))


def _sphere_series(k: float, a: float, r: float, tolerance: float) -> complex:
    ka, kr = k * a, k * r
    # Terms decay like (a/r)^(2n) once n exceeds ka; sum generously past that point.
    n_needed = ka + 4.0 * ka ** (1.0 / 3.0) + 12.0 + np.log(tolerance) / np.log(a / r)
    if not n_needed < _MAX_TERMS:
        msg = (
            "sphere series needs too many terms: the listener is too close to the surface "
            f"(distance/radius = {r / a:.6g})"
        )
        raise ArithmeticError(msg)
    n_max = int(np.ceil(n_needed))
    log_j_a = _log_bessel_j(n_max, ka)
    log_h_a = _log_hankel2(n_max, ka)
    log_h_r = _log_hankel2(n_max, kr)
    n = np.arange(1, n_max + 1)
    log_terms = (
        np.log(2 * n + 1) + _log_derivative(log_j_a, ka) - _log_derivative(log_h_a, ka)
        + 2.0 * log_h_r[1:]
    )  # fmt: skip
    # Order 0 separately: f_0' = -f_1.
    log_zero = log_j_a[1] - log_h_a[1] + 2.0 * log_h_r[0]
    with np.errstate(under="ignore"):
        terms = np.concatenate(([np.exp(log_zero)], np.exp(log_terms)))
    total = complex(terms.sum())
    if abs(terms[-1]) > 1e3 * tolerance * abs(total):  # pragma: no cover - guarded by n_needed
        msg = f"sphere series did not converge (ka={ka:.3g}, kr={kr:.3g})"
        raise ArithmeticError(msg)
    return 1j * k * total


def sphere_echo_ratio(
    frequency_hz: ArrayLike, radius: float, centre_distance: float, c: float = SPEED_OF_SOUND
) -> ComplexArray:
    """Echo ratio of a rigid sphere: its exact echo over that of a wall at its near point.

    At high frequency the magnitude tends to ``radius / centre_distance``, the
    geometrical-acoustics value for reflection from a convex surface.
    """
    wall = plane_echo(frequency_hz, centre_distance - radius, c)
    return np.asarray(sphere_echo(frequency_hz, radius, centre_distance, c) / wall)
