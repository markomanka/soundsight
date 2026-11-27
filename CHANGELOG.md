# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- EXP-0005 concluded: candidate R2 (`soundsight.exercise.render_all_orders`) renders
  trials with diffraction of all orders where the click has energy; it passes accuracy in
  all 36 combinations (R1: 3) but exceeds the cost budget with a broadband click, and
  renders exercises by decision rule 3. Resumable experiment runner; CI re-check and
  official cost measurement.

- Exercise trial renderer (`soundsight.exercise.render`): a click and its echo from one
  disc, with a report of the facts and a screen-reader text. Contributed by Kimi
  (kimi.ai), revised on review (explicit click reference distance, corrected physics in
  the tests, exact fidelity test); candidate R1 of EXP-0005.
- EXP-0005 pre-registered: rendering exercise trials with the accuracy of engine
  increment 2 within a cost budget.

- EXP-0004 candidate C2, edge diffraction of all orders
  (`soundsight.acoustics.candidates.all_orders`): 18 of 18 EXP-0003 levels, every band of
  the gap disc within 0.05 dB, but a full 48 kHz impulse response exceeds the cost budget.
  EXP-0004 concluded: C2 becomes engine increment 2 by decision rule 3.
- CI tests also on Ubuntu 26.04; macOS moved from 15 to 26 (GitHub's current macOS).

- EXP-0004 candidate C1, second-order edge diffraction
  (`soundsight.acoustics.candidates.second_order`), with its weight fixed by a continuity
  test and a fast renderer for millions of arrivals. Evaluated as pre-registered: 15 of
  18 EXP-0003 levels and all 15 size cues, but not accepted (the 5.1 cm disc and the gap
  disc below ka 2 still fail). Not used for exercises until EXP-0004 concludes.

- EXP-0004 pre-registered: the choice between second-order edge diffraction and the
  edge-source integral equation of all orders, with fixed references (checked against
  each other and against the exact small-disk limit), baseline, thresholds and cost
  budgets. Re-checked by the Experiments workflow.
- The wave solver can evaluate echo ratios at any fixed set of frequencies.

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

### Changed

- Supported versions now follow SPEC 0: Python 3.13 or newer (was 3.12), NumPy 2.2 or
  newer (was 1.26), SciPy 1.15 or newer. The policy is written in CONTRIBUTING.md.

- Minimum SciPy raised from 1.11.2 to 1.12.0: candidate C2 uses the iterative solver's
  `rtol` argument, introduced in SciPy 1.12 (caught by the lowest-dependencies CI job).

### Fixed

- The engine's renderer silently truncated its fractional-delay filter for arrivals
  closer to time zero than the filter's half-width; it now refuses them.

- Band levels were averaged over FFT bins, whose positions depend on the recording
  length; on steep spectra this shifted levels by up to 0.54 dB. EXP-0003 and the
  conformance tests now use fixed frequencies. EXP-0003 changed from 12 to 13 levels
  within tolerance and from 9 to 10 trials using the engine (amendment 2).

- The 5 cm reference disk used by the conformance tests ran on a grid coarse enough to
  flatter every model by 0.25 dB; it now uses 12 cells per radius.

- The next-Python job now checks whether the scientific stack runs on that release at all,
  and reports plainly when it does not, instead of failing for reasons unrelated to our code.
