# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Command-line interface: ``soundsight click analyze`` and ``soundsight click synth``.

Exit codes: 0 success, 1 a ``--strict`` analysis found failures, 2 usage or input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import numpy as np

from soundsight import __version__
from soundsight.audio import AudioError, from_array, read_wav, write_wav
from soundsight.click.analysis import analyze_recording
from soundsight.click.qc import PROVISIONAL_PROFILE, Level, assess
from soundsight.click.report import format_text, to_dict
from soundsight.click.synth import ClickParameters, click_train

EXIT_OK = 0
EXIT_FAILED_CHECKS = 1
EXIT_USAGE = 2


def _channel(value: str) -> int | Literal["mean"]:
    if value == "mean":
        return "mean"
    try:
        index = int(value)
    except ValueError:
        msg = f"expected 'mean' or a channel number, got {value!r}"
        raise argparse.ArgumentTypeError(msg) from None
    if index < 0:
        msg = "channel numbers start at 0"
        raise argparse.ArgumentTypeError(msg)
    return index


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (exposed for documentation and tests)."""
    parser = argparse.ArgumentParser(
        prog="soundsight", description="SoundSight: tools for training human echolocation."
    )
    parser.add_argument("--version", action="version", version=f"soundsight {__version__}")
    groups = parser.add_subparsers(dest="group", required=True, metavar="COMMAND")

    click = groups.add_parser("click", help="analyse or synthesize tongue clicks")
    commands = click.add_subparsers(dest="command", required=True, metavar="ACTION")

    analyze = commands.add_parser("analyze", help="check the quality of a click recording")
    analyze.add_argument("file", type=Path, help="WAV file with several clicks")
    analyze.add_argument(
        "--channel", type=_channel, default="mean", help="channel number, or 'mean' (default)"
    )
    analyze.add_argument("--json", action="store_true", help="print a JSON report")
    analyze.add_argument("--verbose", action="store_true", help="list every click")
    analyze.add_argument(
        "--strict", action="store_true", help="exit with status 1 if any check fails"
    )

    synth = commands.add_parser("synth", help="write a synthetic click train to a WAV file")
    synth.add_argument("output", type=Path, help="WAV file to create")
    synth.add_argument("--clicks", type=int, default=10, help="number of clicks (default 10)")
    synth.add_argument("--interval", type=float, default=1.0, help="seconds between clicks")
    synth.add_argument("--peak-hz", type=float, default=3000.0, help="peak frequency in hertz")
    synth.add_argument("--duration-ms", type=float, default=3.0, help="click duration")
    synth.add_argument("--level-dbfs", type=float, default=-6.0, help="click peak level")
    synth.add_argument(
        "--noise-dbfs", type=float, default=-70.0, help="background noise level (RMS)"
    )
    synth.add_argument("--sample-rate", type=int, default=48_000, help="in hertz")
    synth.add_argument("--seed", type=int, default=0, help="random seed for the noise")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return the exit code."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "analyze":
            return _analyze(args)
        return _synth(args)
    except (AudioError, ValueError, OSError) as exc:
        print(f"soundsight: error: {exc}", file=sys.stderr)  # noqa: T201
        return EXIT_USAGE


def _analyze(args: argparse.Namespace) -> int:
    recording = read_wav(args.file)
    analysis = analyze_recording(recording, channel=args.channel)
    findings = assess(analysis, PROVISIONAL_PROFILE)
    source = args.file.name
    if args.json:
        report = to_dict(analysis, findings, PROVISIONAL_PROFILE, source=source)
        sys.stdout.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    else:
        sys.stdout.write(
            format_text(
                analysis, findings, PROVISIONAL_PROFILE, source=source, verbose=args.verbose
            )
        )
    if args.strict and any(f.level is Level.FAIL for f in findings):
        return EXIT_FAILED_CHECKS
    return EXIT_OK


def _synth(args: argparse.Namespace) -> int:
    params = ClickParameters(
        peak_frequency_hz=args.peak_hz,
        duration_ms=args.duration_ms,
        amplitude=float(10.0 ** (args.level_dbfs / 20.0)),
    )
    signal, _ = click_train(
        args.sample_rate,
        args.clicks,
        args.interval,
        params,
        noise_dbfs=args.noise_dbfs,
        seed=args.seed,
    )
    path = write_wav(args.output, from_array(np.clip(signal, -1.0, 1.0), args.sample_rate))
    sys.stdout.write(f"Wrote {args.clicks} synthetic clicks to {path}\n")
    return EXIT_OK
