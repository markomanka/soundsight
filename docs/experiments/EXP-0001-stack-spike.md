# EXP-0001: stack selection for the real-time kernel

Status: protocol drafted 2026-11-15 by Kimi (kimi.ai) with the project lead; reviewed
the same day and **deferred**. It must be revised as described in "Review" before it
runs. The original protocol is kept unchanged below the review.

## Review (2026-11-15)

What is adopted from this protocol now:

- **Decide by experiment, with thresholds fixed in advance.** This is now the rule for
  all experiments (docs/experiments/README.md).
- **Treat integration with a large foreign engine as a risk, not an asset.** The 2016
  lesson, stated as a scoring rule.
- **An independent oracle that candidates must agree with.**
- **Licence hygiene as a scored axis with automatic failure.** Now a CI check for the
  Python code as well (tools/check_dependency_licenses.py).

Why it does not run yet, and what must change first:

1. **The workload predates decision 2.** Image sources to order 3 in a room, judged on
   room parameters, exercises mirror reflection only. EXP-0002 showed that mirror
   reflection alone misjudges training targets by 5 to 16 dB. The workload must be the
   engine of decision 2: image sources, edge diffraction and compact scatterers, run on
   the canonical problems and on EXP-0003.
2. **The oracle must be the reference ladder.** pyroomacoustics (literature D1) has no
   edge diffraction, so agreement with it cannot establish correctness for echolocation.
   It stays useful as a cross-check of the mirror-reflection part. The pass mark for
   every candidate is the conformance matrix, in decibels of echo level, not room
   parameters within a just-noticeable difference (see literature D3 and D5 for why that
   mark is not met even by mature software).
3. **A reference implementation must exist first.** Candidates should be ports of a
   Python implementation that already passes the conformance matrix, so that the spike
   compares languages and not three independent attempts at the physics.
4. **The target is not known yet.** Whether the first real-time target is a phone or a
   desktop decides what "performance" means, and depends on the devices our blind
   co-designers use. The performance budget must come from the physics (an echo from
   distance d arrives after 2d/c, so total latency sets the nearest object that can be
   rendered) and not from a round number.
5. **The candidate list is incomplete.** For pre-rendered exercises the option "keep
   Python for the engine and use the platform's own convolution" needs no new kernel at
   all, and must be on the list as the baseline to beat.
6. **Team familiarity is under-weighted** at a share of 10%. The people most likely to
   maintain a kernel are engineering students; what they can work in matters more than
   the size of a hiring pool.

Trigger to revise and run: a Python engine passing the conformance matrix, and a decision
on the first interactive target (roadmap stage S3).

Note on numbering: the protocol refers to "ADR-0002" for the stack decision. Decision 2
is now the acoustic engine; the stack decision will take the next free number.

---

## Original protocol (unchanged)

## 0. Why a spike before ADR-0002

The 2016 failure mode was a closed engine chosen before measurement. The
stack decision (Rust vs C++ vs other) is therefore made by experiment, with
thresholds fixed in advance. Pre-registration rule: no candidate may be
evaluated on criteria added after results are seen.

## 1. Candidates

| ID | Stack | Role hypothesis |
|----|-------|-----------------|
| R | Rust (compute kernel hand-rolled; kira/cpal-class crates only for I/O, or none) | Primary candidate: no GC, SIMD, safe concurrency, cargo license hygiene |
| C | C++17/20 (STL + Eigen-class; Steam Audio SDK as optional backend) | Incumbent ecosystem; strongest existing room-acoustics code |
| P | Python + pyroomacoustics (baseline oracle, NOT a candidate for the real-time kernel) | Reference correctness: R and C must agree with P within declared epsilon |

Positioning notes (to be validated, not assumed):
- "Erlang + Coq/Rocq": Erlang's strengths (soft real-time distribution,
  fault tolerance) match the future online/competition layer, not
  sample-level DSP (GC, no SIMD-friendly numerics). Re-evaluate at S5.
  Rocq/Coq formal lemmas (docs/quality section 4) are stack-adjacent, not
  stack-binding; Lean is the fallback if Rocq ergonomics block L1–L3.
- If C wins only because of Steam Audio integration value, that must be
  weighed against the 2016 lesson: integration with a large foreign engine
  is scored as a *risk*, not an asset.

## 2. Workload (identical across candidates)

- Input: BRAS-style reference room (shoebox plus one non-convex corner),
  image sources to order 3, frequency-dependent absorption (4 surfaces,
  tabulated coefficients), air absorption on.
- Pose grid: 36 poses (6 positions x 6 yaw steps of 45 deg); IR length 2 s
  at 48 kHz; binaural via one generic HRTF (same SOFA for all candidates).
- Render: convolve the canonical click (from `click synth`) at every pose;
  emit 36 stereo WAVs + a JSON metrics file.

## 3. Metrics and rubric

Pre-registered weights: performance 30%, determinism/reproducibility 20%,
license hygiene 20%, ergonomics/maintainability 20%, ecosystem/risk 10%.

Performance (30): wall time for full grid (median of 5 runs); peak RSS;
single-pose incremental time.
Determinism (20): bit-exact across 3 runs on one machine; across 2 machines
of different OS/arch (tolerance declared in advance); agreement with oracle P
(SNR > 60 dB on corresponding IRs, and ISO 3382 parameters within JND).
License hygiene (20): full dependency-tree audit against the allowlist in
docs/quality; any non-allowlisted transitive dep = automatic fail of this
axis (R starts with an advantage here: no JUCE-class heavyweight).
Ergonomics (20): clean-build time from cold clone; lines of code for the
workload; time for a second developer (simulated: fresh-session prompt) to
locate and modify the crossfade code.
Ecosystem (10): crate/package maturity, team familiarity, hiring pool.

Decision thresholds (fixed now):
- If R scores >= 0.9 x C overall AND R's wall time <= 1.5 x C's -> choose R.
- Else choose C, and record the specific deficit as a follow-up experiment.
- P is never chosen for the kernel; it remains the oracle and the batch
  prototyping tool.

## 4. Experiment log (amend in place)

### Run 1 — TBD
- Date, machine, compiler versions:
- Wall time R / C / P:
- Peak RSS R / C:
- Determinism results:
- Oracle agreement (SNR, ISO 3382 deltas):
- License audit results:
- Ergonomics measurements:
- Scores and decision:

## 5. Reproduction

All spike code and raw measurements must be committed under
`experiments/EXP-0001/` with per-candidate READMEs; CI re-runs the workload
on the reference environment so published numbers are never stale.
