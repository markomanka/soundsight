# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Run every check that CI runs (except the matrix and the network jobs), in order.

Usage, from the repository root:  uv run python tools/check_all.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

CHECKS: list[tuple[str, list[str]]] = [
    ("repository hygiene", [PY, "tools/check_repo_hygiene.py"]),
    ("licensing (REUSE)", [PY, "-m", "reuse", "lint"]),
    ("lint (ruff)", [PY, "-m", "ruff", "check", "."]),
    ("formatting (ruff)", [PY, "-m", "ruff", "format", "--check", "."]),
    ("types (mypy)", [PY, "-m", "mypy"]),
    ("tests with coverage (pytest)", [PY, "-m", "pytest", "--cov", "--cov-report=term"]),
]


def main() -> int:
    """Run all checks; return 1 if any failed."""
    if not (ROOT / ".git").exists():
        print(
            "note: not a git checkout, so the hygiene and REUSE checks cannot read .gitignore "
            "and will also inspect local files such as .venv; run this in a git clone."
        )
    failed = []
    for name, command in CHECKS:
        print(f"\n=== {name} ===", flush=True)
        if subprocess.run(command, cwd=ROOT, check=False).returncode != 0:
            failed.append(name)
    print("\n=== summary ===")
    for name, _ in CHECKS:
        print(f"{'FAILED' if name in failed else 'ok'}: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
