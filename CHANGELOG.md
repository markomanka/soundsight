# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- Acoustics foundation: the decision to use geometric acoustics with edge diffraction
  as the production engine and a wave solver as referee (docs/decisions/0002), exact
  reference solutions, an axisymmetric wave solver validated against them, canonical
  echolocation problems, and a conformance matrix with a declared verdict for every
  model and problem.
- CI job repeating the wave solver's validation on fine grids.

- Click coach: detection, measurement and quality checks of tongue-click recordings,
  with screen-reader-friendly text reports and JSON output (`soundsight click analyze`).
- Synthetic clicks with exactly known properties, for tests and as a neutral default
  stimulus (`soundsight click synth`).
- Continuous integration: hygiene and licence checks, strict linting and typing, tests
  on three operating systems and three Python versions, lowest-dependency and
  next-Python jobs, a regression test on the 2016 recording, package build checks and
  a dependency audit.

### Fixed

- The informational job for the next Python release no longer turns the whole CI run red.
