# 1. A fresh repository under Apache-2.0, not a fork of the 2016 demonstrator

Date: 2026-11-13. Status: accepted.

## Context

The 2016 demonstrator (github.com/SoundSight/SoundSight, two commits, May 2016) is a
modified example application of GSound, a geometric sound propagation library by Carl
Schissler at the University of North Carolina. Its repository holds:

- GSound as a closed, 32-bit binary for Windows and Mac OS X, licensed for educational,
  research and non-profit use only, with commercial use subject to UNC's permission;
- example code from the GSound SDK carrying a "no commercial use" notice;
- about 150 MB of Visual Studio build output;
- no licence of its own.

## Decision

Start a new repository with new history, licensed Apache-2.0, containing none of the
2016 code or binaries.

## Consequences

- No file in this repository is encumbered by GSound's licence, and the history never
  contains its binaries, so the project can be relicensed, distributed through app
  stores, or used commercially by spin-offs without further permission.
- Nothing of value is lost: the 2016 application logic is under 2,000 lines and is
  superseded. Its design ideas are recorded in docs/legacy-2016.md.
- The one asset worth using, a high-quality click recording, has no licence and is not
  redistributed. CI downloads it from the original repository at a pinned commit, with
  a checksum, for a regression test only.
- A CI hygiene check rejects compiled files and oversized files, so the new history
  stays small.
