# EXP-0005: rendering exercise trials with the accuracy of engine increment 2

Status: **pre-registered 2026-11-18.** Protocol and thresholds are fixed; candidate R1 is
frozen in `soundsight.exercise.render`; R2 does not exist yet. Results will be added below
the protocol, which will not be rewritten.

## Question

How should the audio of an exercise trial be rendered so that its echo carries the
accuracy of engine increment 2 (diffraction of all orders, C2 of EXP-0004), at a cost
that lets an exercise pack be precomputed?

## Why

EXP-0004 chose C2 because it alone reproduces every disc of the size-discrimination task
(A3), but a full-band 48 kHz impulse response from C2 does not fit its cost budget. A
trial does not need a full-band response: its audio is the click filtered by the echo, so
errors matter only where the click has energy, and C2's frequency responses are cheap
(about 1 s for 20 frequencies).

## Candidates

| ID | Rendering | Origin |
| --- | --- | --- |
| R1 | First-order diffraction (engine increment 1) rendered in the time domain and convolved with the click. Baseline. | Contributed by Kimi (kimi.ai), 2026-11-18; revised on review (below) |
| R2 | R1 plus diffraction of order two and above from C2, solved at the FFT frequencies of the trial where the click's power spectrum is within 60 dB of its peak, and added by inverse FFT. | To be built |

## Workload (fixed)

The 18 trials of A3's size-discrimination discs (EXP-0003: six diameters at 33, 66 and
99 cm), each with two clicks: the synthetic click of `click synth` (narrow band, about
3 kHz) and the first click of the 2016 recording (a real expert-style click, broader
band), fetched and checked as for EXP-0003. 36 combinations, at 48 kHz.

## Reference and metrics (fixed)

Reference: C2's echo at 200 fixed frequencies spaced logarithmically from 250 Hz to
20 kHz (never FFT bins). A candidate's echo at those frequencies is the discrete-time
Fourier transform of the impulse response it renders, scaled to a unit source.

- **M1, accuracy where the click has energy.** With *C* the click's spectrum,
  E = sum |C|^2 |H_ref - H_cand|^2 / sum |C|^2 |H_ref|^2 over the 200 frequencies.
  Pass: **E at most -25 dB** (about 6% in amplitude; a 1 dB level error alone corresponds
  to about -19 dB).
- **M2, level in the click band.** Echo level from 2 to 4 kHz within **1.0 dB** of C2,
  as in EXP-0003.
- **M3, cost.** Median of three renders of the costliest combination (25.4 cm at 33 cm,
  recorded click), including the audio file, on a standard GitHub ubuntu-24.04 runner:
  at most **120 s**, the budget of EXP-0004 (an exercise pack of about 200 trials
  precomputes overnight).

Thresholds are in `docs/quality/budgets.toml` under `experiments.exp0005`.

## Decision rule (fixed)

1. A candidate is accepted if it passes M1 and M2 for all 36 combinations, and M3.
2. Of accepted candidates the cheaper by M3 renders exercises; R1 is preferred on a tie
   within 20%.
3. If none is accepted, the one passing the most M1 combinations is used, failing trials
   are rendered from wave-solver echoes, and the failed gate is recorded.

## Predictions (recorded 2026-11-18)

- R1 fails M1 and M2 for the 5.1 cm disc at every distance and for the 9.0 cm disc at 66
  and 99 cm, with both clicks (as first order did in EXP-0003), and passes the rest.
- R2 passes M1 and M2 for all 36 combinations.
- R2 passes M3 with the synthetic click; with the recorded click, whose band is wider,
  not predicted.

## Not part of this experiment

The level at which the echo is presented relative to the click depends on what the click
recording stands for (its reference distance, now an explicit parameter) and on the
mouth's directivity and the mouth-to-ear path (B1). That calibration does not affect the
comparison with C2, which is made per unit source, and is an open item for the exercise
pack.

## Clarifications (2026-11-26, recorded before any candidate was measured)

Details the protocol left open, fixed before R2 was frozen and before any combination was
evaluated. No threshold, metric or workload changed.

1. **The recorded click** is the first click the click coach's detector finds in the 2016
   recording, from 1 ms before its start to 2 ms after its end, averaged over the two
   channels and resampled from 192 to 48 kHz (`tools/experiments/exp0005.py`).
2. **R2 solves bins up to 0.45 times the sample rate**, the band in which rendered impulse
   responses are accurate. The recorded click carries energy up to 24 kHz; above 21.6 kHz
   no renderer here is accurate, and the M1 grid ends at 20 kHz.
3. **Polygons.** The reference is C2 on a 48-sided disc, its validated configuration (EXP-0004).
   R1 keeps its frozen 32 sides. R2 adds higher orders solved on the 48-sided disc.
4. **Cost** runs are stopped once they exceed the 120 s budget, as in EXP-0004: the gate is
   pass or fail, and continuing cannot change the verdict.
5. **Re-checking in CI.** The full evaluation takes about one and a half hours, so the
   Experiments workflow recomputes R1 for all 36 combinations and R2 for three of them, and
   compares with the stored results.

## Review of the contributed renderer (R1), 2026-11-18

Kimi (kimi.ai) contributed `soundsight/exercise/render.py`, its tests and the package
file. The contribution has real merit and is integrated: one function renders a trial and
returns a report of its facts; a recording of the user's own click replaces the synthetic
one without other changes; the text report follows the project's screen-reader rules;
band levels use fixed frequencies (EXP-0003, amendment 2); and the tests of determinism,
of the round-trip delay and of distance monotonicity were kept.

Changes made on review, each checked by running the contribution as submitted:

| Finding | Evidence | Change |
| --- | --- | --- |
| The tests read a time budget that was never set, so the suite could not start. | `KeyError: 'exercise'` at collection | Cost is measured here (M3), with its budget pre-registered; the timing test left the unit suite, where shared CI machines make timings unreliable. |
| A test asserted that a disc smaller than the Fresnel zone echoes less than a wall. | The 25.4 cm disc at 33 cm echoed 6.5 dB louder, as EXP-0003 measured with the wave solver (+6.6 dB). | Replaced by a test of the actual physics, in both directions. |
| The direct click was added at the level of a unit source at 1 m, so the report said the echo was 10.1 dB louder than the click. | Report of the 25.4 cm disc at 33 cm | The click's reference distance is an explicit, required parameter and the echo is scaled to it; the report also gives the level relative to a wall. |
| The module stated that it stays inside the validated range of the engine. | First order fails for the 5.1 cm disc and for the 9.0 cm disc at 66 and 99 cm (EXP-0003). | Validity stated as measured; the renderer becomes the baseline of this experiment. |
| An energy inequality used the arrivals' weights in place of the rendered filter, and bounds very loosely. | Inspection | Replaced by an exact fidelity test: the echo in the audio equals the click filtered by the engine's response to 1e-4. |
| The quadrature was limited to 8 kHz while rendering to 24 kHz. | Measured: at most 1e-4 change up to 22 kHz, so harmless. | Simplified to the full band, which costs 4 ms more. |
