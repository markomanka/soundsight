# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Canonical echolocation problems, and the models that answer them.

A *canonical problem* is a scene simple enough to have a trusted reference answer: a
rigid object straight ahead of a listener who emits and hears at the same point. Any
acoustic engine SoundSight adopts, whatever its internals, must be able to answer these
problems, and is accepted only within the range where its answers match the reference
(see docs/acoustics/validation.md). This is what keeps an engine from being a black box.

The models here are deliberately small. Each one isolates one level of physical
approximation, so the test suite can show what each level gets right and wrong:

``SpecularModel``
    Mirror reflection only: what a ray or beam tracer without diffraction computes.
``KirchhoffModel``
    Physical optics: a mirror reflection minus a rim wave with an approximate strength.
``EdgeDiffractionModel``
    Mirror reflection plus first-order diffraction with the correct rim coefficient.
``CompactModel``
    Long-wavelength (Rayleigh) scattering by objects much smaller than the wavelength.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from soundsight.acoustics.reference import analytic
from soundsight.acoustics.reference.analytic import SPEED_OF_SOUND, ComplexArray

#: Band where tongue clicks carry most of their energy, in hertz. Perceptual checks of
#: echo level are made over this band.
CLICK_BAND_HZ = (2000.0, 4000.0)


@dataclass(frozen=True)
class Wall:
    """An infinite rigid wall facing the listener at ``distance`` metres."""

    distance: float


@dataclass(frozen=True)
class Disk:
    """A thin rigid disk facing the listener, centred straight ahead."""

    radius: float
    distance: float


@dataclass(frozen=True)
class Sphere:
    """A rigid sphere straight ahead; ``distance`` is to its nearest point."""

    radius: float
    distance: float


Target = Wall | Disk | Sphere


class UnsupportedTargetError(NotImplementedError):
    """Raised when a model has no answer for a kind of target."""


@runtime_checkable
class EchoModel(Protocol):
    """Anything that can compute the echo ratio of a canonical target.

    The echo ratio is the monostatic echo divided by that of an infinite rigid wall at
    the target's nearest point (see :mod:`soundsight.acoustics.reference.analytic`).
    """

    @property
    def name(self) -> str:
        """Short identifier used in reports and test names."""
        ...

    def echo_ratio(self, target: Target, frequency_hz: ArrayLike) -> ComplexArray:
        """Return the complex echo ratio at each frequency."""
        ...


def _ones(frequency_hz: ArrayLike) -> ComplexArray:
    return np.ones(analytic.wavenumber(frequency_hz).shape, dtype=np.complex128)


@dataclass(frozen=True)
class SpecularModel:
    """Mirror reflections only (geometrical acoustics without diffraction)."""

    c: float = SPEED_OF_SOUND
    name: str = "specular"

    def echo_ratio(self, target: Target, frequency_hz: ArrayLike) -> ComplexArray:
        """Return 1 for any flat target whatever its size; a sphere reflects by its curvature."""
        if isinstance(target, Wall | Disk):
            return _ones(frequency_hz)
        # Reflection from a convex sphere spreads the ray tube: amplitude a / (d + a).
        return _ones(frequency_hz) * target.radius / (target.distance + target.radius)


@dataclass(frozen=True)
class KirchhoffModel:
    """Physical optics for flat targets."""

    c: float = SPEED_OF_SOUND
    name: str = "kirchhoff"

    def echo_ratio(self, target: Target, frequency_hz: ArrayLike) -> ComplexArray:
        """Return the closed-form Kirchhoff integral for the wall and the disk."""
        if isinstance(target, Wall):
            return _ones(frequency_hz)
        if isinstance(target, Disk):
            return analytic.disk_echo_ratio_kirchhoff(
                frequency_hz, target.radius, target.distance, self.c
            )
        raise UnsupportedTargetError(f"{self.name} has no model for {type(target).__name__}")


@dataclass(frozen=True)
class EdgeDiffractionModel:
    """Mirror reflection plus first-order edge diffraction for flat targets."""

    c: float = SPEED_OF_SOUND
    name: str = "edge-diffraction"

    def echo_ratio(self, target: Target, frequency_hz: ArrayLike) -> ComplexArray:
        """Return the specular term plus the rim wave with the exact rigid-edge coefficient."""
        if isinstance(target, Wall):
            return _ones(frequency_hz)
        if isinstance(target, Disk):
            return analytic.disk_echo_ratio_edge_diffraction(
                frequency_hz, target.radius, target.distance, self.c
            )
        raise UnsupportedTargetError(f"{self.name} has no model for {type(target).__name__}")


@dataclass(frozen=True)
class CompactModel:
    """Long-wavelength scattering by small rigid objects."""

    c: float = SPEED_OF_SOUND
    name: str = "compact"

    def echo_ratio(self, target: Target, frequency_hz: ArrayLike) -> ComplexArray:
        """Return Rayleigh-limit monopole and dipole scattering."""
        if isinstance(target, Disk):
            return analytic.compact_disk_echo_ratio(
                frequency_hz, target.radius, target.distance, self.c
            )
        if isinstance(target, Sphere):
            return analytic.compact_sphere_echo_ratio(
                frequency_hz, target.radius, target.distance + target.radius, self.c
            )
        raise UnsupportedTargetError(f"{self.name} has no model for {type(target).__name__}")


def exact_echo_ratio(
    target: Wall | Sphere, frequency_hz: ArrayLike, c: float = SPEED_OF_SOUND
) -> ComplexArray:
    """Exact echo ratio of the targets that have a closed-form solution."""
    if isinstance(target, Wall):
        return _ones(frequency_hz)
    return analytic.sphere_echo_ratio(
        frequency_hz, target.radius, target.distance + target.radius, c
    )


def band_level_db(ratio: ComplexArray, weights: NDArray[np.float64] | None = None) -> float:
    """Echo level over a band, in dB relative to a wall: ``10 log10(mean |E|^2)``.

    ``weights`` (for example a click's power spectrum) emphasise parts of the band.
    Differences of about 1 dB in level are at the threshold of what listeners notice,
    which is why acceptance thresholds are stated in this unit.
    """
    power = np.abs(np.asarray(ratio)) ** 2
    mean = float(np.average(power, weights=weights))
    if mean <= 0.0:
        return float("-inf")
    return float(10.0 * np.log10(mean))
