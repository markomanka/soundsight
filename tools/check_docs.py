# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Fail if a decision record does not cite its evidence, or cites something that is missing.

Rules (proposed by Kimi, kimi.ai, as the "docs-drift check"; see docs/quality/quality-gates.md):

* every file in docs/decisions/ has a line starting with "Literature:" and one starting
  with "Experiments:";
* each cites at least one identifier, or says "none" followed by a reason in brackets;
* every literature identifier cited exists in docs/research/literature.md, and every
  experiment identifier is a file in docs/experiments/;
* identifiers in the literature register are unique, and each entry names a consumer.

Usage, from the repository root:  python tools/check_docs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LITERATURE_ID = re.compile(r"\b[A-Z][0-9]{1,2}\b")
EXPERIMENT_ID = re.compile(r"\bEXP-[0-9]{4}\b")
REGISTER_ROW = re.compile(r"^\|\s*([A-Z][0-9]{1,2})\s*\|(.*)\|\s*$")
NONE_WITH_REASON = re.compile(r"^none\s*\(.{10,}\)\.?$", re.IGNORECASE)


def register_ids(register_text: str) -> tuple[dict[str, list[str]], list[str]]:
    """Return {id: columns} for the literature register, and problems found in it."""
    entries: dict[str, list[str]] = {}
    problems = []
    for line in register_text.splitlines():
        match = REGISTER_ROW.match(line)
        if not match:
            continue
        identifier = match.group(1)
        columns = [c.strip() for c in match.group(2).split("|")]
        if identifier in entries:
            problems.append(f"literature register: identifier {identifier} appears twice")
        entries[identifier] = columns
        # Columns after the identifier: citation, then the consumer.
        consumer = columns[1] if len(columns) > 1 else ""
        if not consumer:
            problems.append(f"literature register: {identifier} names no consumer")
    return entries, problems


def _cited(text: str, label: str) -> str | None:
    for line in text.splitlines():
        if line.startswith(f"{label}:"):
            return line[len(label) + 1 :].strip()
    return None


def check_decision(name: str, text: str, literature: set[str], experiments: set[str]) -> list[str]:
    """Return the problems with one decision record."""
    problems = []
    for label, pattern, known, what in (
        ("Literature", LITERATURE_ID, literature, "docs/research/literature.md"),
        ("Experiments", EXPERIMENT_ID, experiments, "docs/experiments/"),
    ):
        cited = _cited(text, label)
        if cited is None:
            problems.append(f"{name}: no '{label}:' line")
            continue
        if NONE_WITH_REASON.match(cited):
            continue
        ids = pattern.findall(cited)
        if not ids:
            problems.append(
                f"{name}: '{label}:' cites nothing; give identifiers or 'none (reason)'"
            )
        problems.extend(
            f"{name}: {label.lower()} {i} is not in {what}" for i in ids if i not in known
        )
    return problems


def check_repository(root: Path = ROOT) -> list[str]:
    """Check every decision record under root."""
    register = root / "docs" / "research" / "literature.md"
    if not register.is_file():
        return ["docs/research/literature.md is missing"]
    entries, problems = register_ids(register.read_text(encoding="utf-8"))
    experiments = {
        m.group(0)
        for p in (root / "docs" / "experiments").glob("EXP-*.md")
        if (m := EXPERIMENT_ID.match(p.name))
    }
    decisions = sorted((root / "docs" / "decisions").glob("[0-9]*.md"))
    if not decisions:
        problems.append("no decision records found in docs/decisions/")
    for path in decisions:
        problems += check_decision(
            path.name, path.read_text(encoding="utf-8"), set(entries), experiments
        )
    return problems


def main() -> int:
    """Run the check and report."""
    problems = check_repository()
    for problem in problems:
        print(f"docs: {problem}", file=sys.stderr)
    if problems:
        return 1
    print("docs: every decision record cites existing literature and experiments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
