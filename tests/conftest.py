# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures and Hypothesis profiles."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings

# "ci" is deterministic (same examples every run, so CI is never flaky) and broader;
# "dev" is randomised, so local runs keep exploring new cases, and fast.
settings.register_profile(
    "ci", max_examples=60, deadline=None, derandomize=True, database=None, print_blob=True
)
settings.register_profile(
    "dev", max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))

REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_CLICK = REPO_ROOT / "data" / "legacy" / "clickrecord.wav"


@pytest.fixture
def legacy_click() -> Path:
    """Path to the 2016 click recording; skip (or fail in CI) when it is absent."""
    if not LEGACY_CLICK.is_file():
        if os.environ.get("SOUNDSIGHT_REQUIRE_LEGACY") == "1":
            pytest.fail(f"legacy recording required but missing: {LEGACY_CLICK}")
        pytest.skip("legacy recording not present; run tools/fetch_legacy_click.py")
    return LEGACY_CLICK
