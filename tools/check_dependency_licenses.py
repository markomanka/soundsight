# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Fail if an installed dependency's licence is unknown or outside the allowlist.

The policy lives in docs/quality/licenses.toml. Packages that SoundSight needs at run
time (found by following its declared requirements) must carry a permissive licence;
everything else in the environment is a development tool and may also be copyleft.

Usage, from the repository root:  uv run python tools/check_dependency_licenses.py
"""

from __future__ import annotations

import re
import sys
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docs" / "quality" / "licenses.toml"
PROJECT = "soundsight"

#: Trove classifiers that identify exactly one licence. Ambiguous ones ("BSD License")
#: are deliberately absent: they need a reviewed override.
CLASSIFIERS = {
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
}
#: Common non-SPDX spellings found in the free-text License field.
ALIASES = {"Apache 2.0": "Apache-2.0", "Apache License 2.0": "Apache-2.0", "BSD-3": "BSD-3-Clause"}
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]*")
_OPERATORS = {"AND", "OR", "WITH"}
#: A free-text field longer than this many words is prose, not a licence expression.
_MAX_EXPRESSION_TOKENS = 15


@dataclass(frozen=True)
class Policy:
    """The allowlists and reviewed overrides."""

    runtime: frozenset[str]
    development: frozenset[str]
    overrides: Mapping[str, str]


def load_policy(path: Path = POLICY) -> Policy:
    """Read the policy file."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    runtime = frozenset(data["runtime"]["allowed"])
    development = runtime | frozenset(data["development"]["allowed"])
    overrides: dict[str, str] = {}
    for name, entry in data.get("overrides", {}).items():
        if not {"license", "reviewed", "note"} <= entry.keys():
            msg = f"override for {name} must have license, reviewed and note"
            raise ValueError(msg)
        overrides[canonicalize_name(name)] = entry["license"]
    return Policy(runtime, development, overrides)


def identifiers(expression: str) -> list[str]:
    """Return the licence identifiers in an SPDX expression (operators removed)."""
    return [t for t in _IDENTIFIER.findall(expression) if t.upper() not in _OPERATORS]


def is_allowed(expression: str, allowed: frozenset[str]) -> bool:
    """Decide whether an SPDX expression is acceptable.

    A OR B (a choice offered to us) passes if either side passes; everything else,
    including bracketed expressions, passes only if every identifier is allowed.
    """
    if "(" not in expression and " OR " in expression:
        return any(is_allowed(part, allowed) for part in expression.split(" OR "))
    ids = identifiers(expression)
    return bool(ids) and all(i in allowed for i in ids)


def _reads_as_spdx(text: str) -> bool:
    """Tell an SPDX expression from free text (a copyright line, a sentence)."""
    tokens = text.replace("(", " ").replace(")", " ").split()
    if not 0 < len(tokens) <= _MAX_EXPRESSION_TOKENS or not all(
        _IDENTIFIER.fullmatch(t) for t in tokens
    ):
        return False
    return len(tokens) == 1 or any(t.upper() in _OPERATORS for t in tokens)


def declared_license(
    name: str, meta: Mapping[str, object], overrides: Mapping[str, str]
) -> str | None:
    """Return a package's licence expression, or None if it cannot be determined."""
    if name in overrides:
        return overrides[name]
    expression = meta.get("License-Expression")
    if isinstance(expression, str) and expression.strip():
        return expression.strip()
    text = meta.get("License")
    if isinstance(text, str) and text.strip():
        first = text.strip().splitlines()[0].strip()
        first = ALIASES.get(first, first)
        if _reads_as_spdx(first):
            return first
    classifiers = meta.get("classifiers")
    found = (
        [CLASSIFIERS[c] for c in classifiers if c in CLASSIFIERS]
        if isinstance(classifiers, list)
        else []
    )
    if len(set(found)) == 1:
        return found[0]
    return None


def runtime_closure(requirements: Mapping[str, Iterable[str]], root: str = PROJECT) -> set[str]:
    """Return the packages reachable from root through unconditional requirements."""
    seen: set[str] = set()
    stack = [canonicalize_name(root)]
    while stack:
        name = stack.pop()
        for line in requirements.get(name, ()):
            try:
                requirement = Requirement(line)
            except InvalidRequirement:
                continue
            if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
                continue
            dependency = canonicalize_name(requirement.name)
            if dependency not in seen:
                seen.add(dependency)
                stack.append(dependency)
    return seen


def audit(
    packages: Mapping[str, Mapping[str, object]],
    requirements: Mapping[str, Iterable[str]],
    policy: Policy,
    root: str = PROJECT,
) -> list[str]:
    """Return one message per package that violates the policy."""
    runtime = runtime_closure(requirements, root)
    problems = []
    for name in sorted(packages):
        if name == canonicalize_name(root):
            continue
        kind, allowed = (
            ("runtime", policy.runtime) if name in runtime else ("development", policy.development)
        )
        licence = declared_license(name, packages[name], policy.overrides)
        if licence is None:
            problems.append(
                f"{name} ({kind}): licence cannot be determined; review it and add an override"
            )
        elif not is_allowed(licence, allowed):
            problems.append(f"{name} ({kind}): licence {licence!r} is not on the {kind} allowlist")
    return problems


def installed() -> tuple[dict[str, dict[str, object]], dict[str, list[str]]]:
    """Collect licence metadata and requirements of every installed distribution."""
    packages: dict[str, dict[str, object]] = {}
    requirements: dict[str, list[str]] = {}
    for dist in metadata.distributions():
        name = canonicalize_name(dist.metadata["Name"])
        packages[name] = {
            "License-Expression": dist.metadata.get("License-Expression"),
            "License": dist.metadata.get("License"),
            "classifiers": dist.metadata.get_all("Classifier") or [],
        }
        requirements[name] = list(dist.requires or [])
    return packages, requirements


def main() -> int:
    """Audit the current environment."""
    policy = load_policy()
    packages, requirements = installed()
    if canonicalize_name(PROJECT) not in packages:
        print(f"licences: {PROJECT} is not installed in this environment", file=sys.stderr)
        return 1
    problems = audit(packages, requirements, policy)
    for problem in problems:
        print(f"licences: {problem}", file=sys.stderr)
    if problems:
        print(f"licences: policy and overrides are in {POLICY.relative_to(ROOT)}", file=sys.stderr)
        return 1
    runtime = sorted(runtime_closure(requirements))
    print(f"licences: {len(packages) - 1} packages checked; runtime: {', '.join(runtime)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
