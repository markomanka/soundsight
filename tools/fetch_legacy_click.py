# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Download the 2016 click recording used by the legacy regression test.

The file comes from the original SoundSight demonstrator repository, pinned to its last
commit and verified by SHA-256, and is saved to data/legacy/ (ignored by git). It is
used only for testing and is not redistributed: that repository carries no licence.

Usage: python tools/fetch_legacy_click.py
"""

from __future__ import annotations

import hashlib
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "legacy" / "clickrecord.wav"
COMMIT = "0dd3a1c5a8824173de0174133d56279c8497457f"
URL = f"https://raw.githubusercontent.com/SoundSight/SoundSight/{COMMIT}/Debug/Data/clickrecord.wav"
SHA256 = "f95205aee10a4234578aad81bcde7e652118d58d08e59956fe743faeea1bafeb"
ATTEMPTS = 4


def sha256_of(path: Path) -> str:
    """Return the hex SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def is_valid(path: Path, expected: str = SHA256) -> bool:
    """Return whether path exists and has the expected digest."""
    return path.is_file() and sha256_of(path) == expected


def fetch(dest: Path = DEST, url: str = URL, expected: str = SHA256) -> Path:
    """Download url to dest unless a verified copy is already there."""
    if is_valid(dest, expected):
        print(f"legacy: already present and verified: {dest}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(".part")
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - fixed https URL
                partial.write_bytes(response.read())
            break
        except OSError as exc:
            if attempt == ATTEMPTS:
                raise
            print(f"legacy: attempt {attempt} failed ({exc}); retrying", file=sys.stderr)
            time.sleep(2**attempt)
    if not is_valid(partial, expected):
        partial.unlink(missing_ok=True)
        msg = f"checksum mismatch for {url}"
        raise RuntimeError(msg)
    partial.replace(dest)
    print(f"legacy: downloaded and verified: {dest}")
    return dest


if __name__ == "__main__":
    fetch()
