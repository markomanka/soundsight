# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Tongue-click synthesis, detection, measurement and quality checks."""

from soundsight.click.analysis import ClickAnalysis, SessionSummary, analyze_recording
from soundsight.click.detect import ClickEvent, Detection, DetectionSettings, detect_clicks
from soundsight.click.features import ClickFeatures, measure_click
from soundsight.click.qc import PROVISIONAL_PROFILE, Finding, Level, ReferenceProfile, assess
from soundsight.click.synth import ClickParameters, click_train, synth_click

__all__ = [
    "PROVISIONAL_PROFILE",
    "ClickAnalysis",
    "ClickEvent",
    "ClickFeatures",
    "ClickParameters",
    "Detection",
    "DetectionSettings",
    "Finding",
    "Level",
    "ReferenceProfile",
    "SessionSummary",
    "analyze_recording",
    "assess",
    "click_train",
    "detect_clicks",
    "measure_click",
    "synth_click",
]
