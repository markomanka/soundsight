# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""SoundSight: open tools for training human echolocation."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("soundsight")
except PackageNotFoundError:  # pragma: no cover - only when running from an uninstalled tree
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
