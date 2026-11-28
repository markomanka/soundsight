# Quality gates

How each stage's success is measured, decided before the stage is built. Stages are
defined in [docs/roadmap.md](../roadmap.md); thresholds that CI enforces are in
[budgets.toml](budgets.toml); the dependency licence policy is in
[licenses.toml](licenses.toml).

Origin: drafted by Kimi (kimi.ai) with the project lead on 2026-11-15, then reviewed
against decision 2, the test suite and the literature. Section 5 lists what was changed
and why.

## 1. Principles

1. Every accuracy or performance number in a decision record is reproducible by CI from
   committed files, in a pinned environment.
2. Any output a decision depends on is pinned: a numeric tolerance in a test, or a
   stored file with a hash and the command that regenerates it.
3. Determinism is a feature: seeded generation, a locked dependency set, and results
   that agree across platforms within a stated tolerance.
4. No benchmark without a budget: a number means something only against a threshold
   fixed before the measurement (docs/experiments/README.md).
5. A gate measures what the listener needs. An accuracy gate is stated in the units of a
   perceptual threshold wherever one is known.

Five axes throughout: code quality, reproducibility, stability, performance, and
external validity (does it hold against measurements and against users?).

## 2. Stage gates

Status: [x] met and enforced by CI; [ ] open.

### S1. Click coach

- [x] Detection and measurement recover synthetic ground truth at four sample rates;
      property tests cover gain, time shift and polarity; pure noise yields no clicks.
- [x] Regression test on a real recording, pinned by commit and checksum.
- [ ] Reference ranges calibrated: cite B1 in the code, then confirm with at least one
      echolocation instructor. Until then the profile stays labelled provisional.
- [ ] Three or more screen-reader users complete the analysis unaided; anything that
      stops them is filed as a bug.

### S2. Acoustic engine and first exercise pack

- [x] Reference ladder in CI: exact solutions, a wave solver validated against them, and
      a conformance matrix with a declared verdict per model and problem.
- [x] EXP-0003 run: 13 of 18 levels and 12 of 15 size cues within the pre-registered
      tolerances (after the correction of 2026-11-17); the 5 remaining trials use
      wave-solver echoes. Re-run weekly and on every change to the acoustics code.
- [x] Engine laws enforced by CI: continuity at reflection boundaries, reciprocity,
      scale invariance, wall limit, convergence, impulse-response fidelity.
- [x] EXP-0004 concluded: C2 (all orders) passes all of EXP-0003, the gap disc in every
      band and the physical-law tests; it fails the full-band impulse-response budget and
      becomes engine increment 2 by decision rule 3.
- [ ] Exercise audio rendered with C2 within a cost budget (next experiment).
- [ ] Canonical problems added, each with a reference, for: the 80 x 20 cm rectangle at
      four orientations (A3); a thin pole; an object off axis; two ears.
- [ ] Measured rung: simulated against measured impulse responses for at least one
      simple scene of E3 (reflection and diffraction at a finite plate), reported in the
      same decibel units.
- [ ] Room reverberation, when added: parameters of E1 reported in JND units against a
      measured room. The pass mark is set from the state of the art (D5), not at one JND,
      which input-data uncertainty puts out of reach (D3).
- [x] Each exercise file of pack v0 is listed with its SHA-256 and reproduced by
      regeneration (tested); the stored disc caches are checked against a fresh computation.
- [ ] Exercises follow A3's structure, including mirror-image transfer mazes and the
      no-click control.
- [ ] Three or more blind co-designers complete each exercise unaided.
- [ ] A protocol, approved by an ethics committee, for testing whether training
      transfers to real navigation. Without it no claim of effectiveness is made.

### S3. Interactive listening with head tracking

- [ ] EXP-0001 revised and run; the stack decision cites it.
- [ ] Switching between pre-computed responses as the head turns is inaudible: ABX test
      with five listeners, at chance.
- [ ] Front-back confusion rate with the generic HRTF measured with and without head
      tracking (F1).
- [ ] Performance budgets for the target device, derived from the task and fixed before
      measuring, in budgets.toml.

### S4. Personal scenes

- [ ] Ten real rooms reconstructed; room dimensions within 5 cm of a tape measure.
- [ ] The scanning and annotation flow passes a screen-reader audit: three users,
      thinking aloud, every task completed without sighted help.
- [ ] For each room, simulated echoes compared with echoes recorded in it; the error is
      tracked over time.
- [ ] Scans never leave the device without the user's explicit choice.

### S5. Live clicks on dedicated hardware

- [ ] **Absolute** latency from microphone to headphones measured and shown to the user,
      together with the nearest distance it allows: d_min = c x latency / 2. An object
      nearer than d_min is not offered.
- [ ] Latency jitter at the 99th percentile no more than 0.1 ms: jitter is heard as a
      change of distance, and 0.1 ms is 1.7 cm. Provisional; to be set against the
      distance-discrimination thresholds summarised in A2 before this stage starts.
- [ ] Tasks that depend on timing stay pre-rendered on any setup that has not passed the
      two gates above.
- [ ] Virtual echoes compared with real ones for the same object and listener.

## 3. Continuous integration

| Check | State |
| --- | --- |
| Formatting, lint, strict types, tests with coverage of at least 95% | In place |
| Tests on three operating systems and three Python versions; lowest supported dependencies | In place |
| Repository hygiene (no binaries, no large files) and REUSE licence declarations | In place |
| Known-vulnerability audit of the locked dependencies | In place |
| Regression on a real recording, pinned by commit and checksum | In place |
| Acoustic reference ladder and conformance matrix; fine-grid job | In place |
| **Dependency licence allowlist** (`tools/check_dependency_licenses.py`): any dependency with an unknown or unlisted licence fails the build | Added with this document |
| **Evidence citations** (`tools/check_docs.py`): every decision record cites existing literature and experiments | Added with this document |
| **Budgets in one file** read by the tests | Added with this document |
| **Pre-registered experiments re-run** (`experiments.yml`): EXP-0003 weekly and on every change to the acoustics code, failing if any stored level moves by more than 0.02 dB or any verdict changes | Added with engine increment 1 |
| Stored exercise files with hashes | With the first exercise pack (S2) |
| Performance budgets, failing on regression | With the first code that has a budget (S3) |
| Nightly determinism job across platforms | With the engine (S2); today the matrix already runs identical numeric assertions on three systems |

## 4. Formal proofs: not now

The draft proposed machine-checked proofs (Rocq or Lean) of three kernel properties.
They are not adopted at this stage, for these reasons.

- **Partition of unity in a crossfade** and **delay equals path length over the speed of
  sound** are one-line identities; a property test covers them at negligible cost, and a
  proof about real numbers would not cover the floating-point code that actually runs.
- **"Output energy never exceeds input energy times a surface bound" is false as
  stated.** Interference is physical: a disk covering one Fresnel zone returns more than
  twice the echo amplitude of an infinite wall (measured in EXP-0002, and classical
  optics). A lemma of this form would either be wrong or would forbid correct physics.
  The property worth guarding is conservation of energy in the wave solver, which a test
  already checks to one part in a billion.
- Delays must be accurate to a fraction of a sample, not "sample-accurate": one sample at
  48 kHz is 3.6 mm of distance, and interpolation error is what needs a bound.

Revisit when the real-time kernel exists and is stable. The draft's cost-benefit rule is
kept: prove only what a property test cannot cover with similar confidence.

## 5. What changed from the 2026-11-15 draft, and why

- **The room gate is no longer the main accuracy gate.** Room parameters within one JND
  of a measured room describe reverberation for speech and music, not the early echoes of
  nearby objects, and mature software does not meet that mark (D3, D5). The main gates
  are echo levels of canonical objects in decibels; the room gate remains for
  reverberation.
- **pyroomacoustics is a cross-check, not the oracle:** it has no edge diffraction.
- **The latency gate bounds absolute latency,** which sets the nearest renderable object;
  the draft bounded only jitter.
- **Stages reordered** to put pre-rendered, triggered listening before any live-click
  mode, and to make transfer to real navigation an explicit gate.
- **Coverage** stays at the 95% already enforced, above the draft's 85%.
- **Formal proofs** deferred (section 4).
- **Kept as proposed:** the four principles, stage gates with exit criteria, budgets in
  one versioned file, the licence allowlist, the evidence-citation check, stored files
  with hashes, screen-reader task-completion gates, and pre-registration.
