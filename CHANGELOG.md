# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- Acoustic engine, increment 1 (`soundsight.acoustics.engine`): echoes of a thin convex
  rigid plate by image source plus first-order Biot-Tolstoy-Medwin edge diffraction, as
  exact frequency responses or impulse responses at any sample rate; validated by
  physical-law tests and admitted through the conformance matrix.
- EXP-0003 run as pre-registered: the engine is valid for 9 of 15 trials of the
  size-discrimination task; a CI workflow re-runs it weekly and on acoustics changes.

- Acoustics foundation: the decision to use geometric acoustics with edge diffraction
  as the production engine and a wave solver as referee (docs/decisions/0002), exact
  reference solutions, an axisymmetric wave solver validated against them, canonical
  echolocation problems, and a conformance matrix with a declared verdict for every
  model and problem.
- CI job repeating the wave solver's validation on fine grids.
- Plan of record: roadmap, quality gates per stage, a research base checked against
  PubMed, and experiment records with a pre-registration rule, including the
  pre-registered EXP-0003 on the size-discrimination discs of a published training
  study. Structure and first drafts contributed by Kimi (kimi.ai).
- CI guards: a dependency-licence allowlist with reviewed overrides, and a check that
  every decision record cites existing literature and experiments.
- Test tolerances read from a single versioned budgets file.

- Click coach: detection, measurement and quality checks of tongue-click recordings,
  with screen-reader-friendly text reports and JSON output (`soundsight click analyze`).
- Synthetic clicks with exactly known properties, for tests and as a neutral default
  stimulus (`soundsight click synth`).
- Continuous integration: hygiene and licence checks, strict linting and typing, tests
  on three operating systems and three Python versions, lowest-dependency and
  next-Python jobs, a regression test on the 2016 recording, package build checks and
  a dependency audit.

### Fixed

- The 5 cm reference disk used by the conformance tests ran on a grid coarse enough to
  flatter every model by 0.25 dB; it now uses 12 cells per radius.

- The next-Python job now checks whether the scientific stack runs on that release at all,
  and reports plainly when it does not, instead of failing for reasons unrelated to our code.
