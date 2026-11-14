# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Fail if the repository tracks build artefacts, binaries or oversized files.

The 2016 demonstrator repository was 155 MB, almost all of it compiled output and a
third-party binary library. This check keeps that from happening again. It inspects
the files git tracks (or, outside a git checkout, every file under the repository).

Usage: python tools/check_repo_hygiene.py
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 512 * 1024

#: Compiled output, IDE state and binary libraries: never source.
FORBIDDEN_SUFFIXES = frozenset(
    {
        ".a", ".class", ".dll", ".dylib", ".exe", ".idb", ".ilk", ".lib", ".o", ".obj",
        ".pch", ".pdb", ".pyc", ".pyd", ".sdf", ".so", ".suo", ".tlog",
    }
)  # fmt: skip
#: Directory names that only ever hold generated content.
FORBIDDEN_DIRS = frozenset({"__pycache__", ".vs", "Debug", "Release", "build", "dist", ".venv"})
#: Outside a git checkout we cannot read .gitignore, so skip what it would ignore.
SKIP_DIRS = FORBIDDEN_DIRS | {
    ".git",
    ".hypothesis",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "data",
    "htmlcov",
}
SKIP_FILES = frozenset({".coverage", "coverage.xml"})


def tracked_files(root: Path = ROOT) -> list[Path]:
    """Return files tracked by git, or all files when not in a git checkout."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],  # noqa: S607 - git from PATH is intended
            cwd=root,
            capture_output=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return [
            p.relative_to(root)
            for p in root.rglob("*")
            if p.is_file()
            and p.name not in SKIP_FILES
            and not SKIP_DIRS.intersection(p.relative_to(root).parts)
        ]
    return [Path(name) for name in out.decode().split("\0") if name]


def violations(paths: Iterable[Path], root: Path = ROOT, max_bytes: int = MAX_BYTES) -> list[str]:
    """Return one message per offending file."""
    problems = []
    for rel in sorted(paths):
        full = root / rel
        if rel.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"{rel}: compiled or binary file type {rel.suffix!r} is not allowed")
        elif FORBIDDEN_DIRS.intersection(rel.parts[:-1]):
            problems.append(f"{rel}: lives in a directory for generated files")
        elif full.is_file() and full.stat().st_size > max_bytes:
            size_kib = full.stat().st_size // 1024
            problems.append(f"{rel}: {size_kib} KiB exceeds the {max_bytes // 1024} KiB limit")
    return problems


def main() -> int:
    """Run the check and report the result."""
    files = tracked_files()
    problems = violations(files)
    for problem in problems:
        print(f"hygiene: {problem}", file=sys.stderr)
    if problems:
        print(
            "hygiene: data and media belong in releases or external storage, with a licence "
            "and the recorded person's consent; see CONTRIBUTING.md",
            file=sys.stderr,
        )
        return 1
    print(f"hygiene: {len(files)} files checked, no problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
