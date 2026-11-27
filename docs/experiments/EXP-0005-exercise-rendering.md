# EXP-0005: rendering exercise trials with the accuracy of engine increment 2

Status: pre-registered 2026-11-18; run 2026-11-26 to 27. **Concluded: no candidate passes
every gate; by decision rule 3, R2 renders exercises, and the cost of trials with broadband
clicks is the next problem.** Results are below the protocol, which has not been rewritten.

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

## Results (2026-11-27)

R1: `soundsight.exercise.render` as frozen on 2026-11-18 (contributed by Kimi, revised on
review). R2: `soundsight.exercise.render_all_orders`, frozen at commit `f403209`
before any combination was evaluated. All 36 combinations were computed with a resumable
runner (`tools/experiments/exp0005.py`); every number is stored in `EXP-0005-results.json`
and the Experiments workflow recomputes R1 in full and R2 on three combinations.

### M1 and M2 per combination

M1: click-weighted error against C2 (pass at most -25 dB). M2: band level against C2
(pass within 1.0 dB).

| Click | Diameter (cm) | Distance (cm) | R1 M1 (dB) | R1 M2 (dB) | R2 M1 (dB) | R2 M2 (dB) |
| --- | --- | --- | --- | --- | --- | --- |
| recorded | 5.1 | 33 | -1.0 FAIL | +1.95 FAIL | -40.2 pass | +0.004 pass |
| recorded | 5.1 | 66 | -0.7 FAIL | +1.90 FAIL | -41.3 pass | +0.005 pass |
| recorded | 5.1 | 99 | -0.6 FAIL | +1.89 FAIL | -42.8 pass | +0.005 pass |
| recorded | 9.0 | 33 | -11.4 FAIL | -0.97 pass | -48.7 pass | +0.002 pass |
| recorded | 9.0 | 66 | -10.8 FAIL | -1.12 FAIL | -49.6 pass | +0.001 pass |
| recorded | 9.0 | 99 | -10.6 FAIL | -1.17 FAIL | -51.1 pass | +0.001 pass |
| recorded | 13.5 | 33 | -16.4 FAIL | +0.29 pass | -50.9 pass | +0.001 pass |
| recorded | 13.5 | 66 | -15.7 FAIL | +0.32 pass | -51.8 pass | +0.001 pass |
| recorded | 13.5 | 99 | -15.5 FAIL | +0.32 pass | -53.3 pass | +0.001 pass |
| recorded | 17.5 | 33 | -18.8 FAIL | +0.04 pass | -52.8 pass | +0.001 pass |
| recorded | 17.5 | 66 | -18.2 FAIL | +0.02 pass | -53.9 pass | +0.001 pass |
| recorded | 17.5 | 99 | -17.9 FAIL | +0.01 pass | -55.2 pass | +0.001 pass |
| recorded | 22.9 | 33 | -22.7 FAIL | -0.01 pass | -54.9 pass | +0.001 pass |
| recorded | 22.9 | 66 | -22.2 FAIL | +0.05 pass | -56.3 pass | +0.001 pass |
| recorded | 22.9 | 99 | -22.0 FAIL | +0.07 pass | -57.7 pass | +0.001 pass |
| recorded | 25.4 | 33 | -23.7 FAIL | -0.06 pass | -55.3 pass | +0.001 pass |
| recorded | 25.4 | 66 | -23.4 FAIL | -0.05 pass | -56.8 pass | +0.001 pass |
| recorded | 25.4 | 99 | -23.3 FAIL | -0.05 pass | -58.3 pass | +0.001 pass |
| synthetic | 5.1 | 33 | -1.3 FAIL | +1.95 FAIL | -43.9 pass | +0.005 pass |
| synthetic | 5.1 | 66 | -1.0 FAIL | +1.90 FAIL | -45.0 pass | +0.005 pass |
| synthetic | 5.1 | 99 | -1.0 FAIL | +1.89 FAIL | -48.1 pass | +0.005 pass |
| synthetic | 9.0 | 33 | -13.9 FAIL | -0.97 pass | -53.4 pass | +0.001 pass |
| synthetic | 9.0 | 66 | -13.2 FAIL | -1.12 FAIL | -53.9 pass | +0.001 pass |
| synthetic | 9.0 | 99 | -13.0 FAIL | -1.17 FAIL | -56.2 pass | +0.001 pass |
| synthetic | 13.5 | 33 | -18.0 FAIL | +0.29 pass | -58.2 pass | +0.001 pass |
| synthetic | 13.5 | 66 | -17.1 FAIL | +0.32 pass | -55.8 pass | +0.001 pass |
| synthetic | 13.5 | 99 | -16.7 FAIL | +0.32 pass | -57.2 pass | +0.001 pass |
| synthetic | 17.5 | 33 | -20.5 FAIL | +0.04 pass | -61.6 pass | +0.001 pass |
| synthetic | 17.5 | 66 | -19.4 FAIL | +0.02 pass | -58.6 pass | +0.001 pass |
| synthetic | 17.5 | 99 | -18.9 FAIL | +0.01 pass | -59.9 pass | +0.001 pass |
| synthetic | 22.9 | 33 | -25.4 pass | -0.01 pass | -62.3 pass | +0.001 pass |
| synthetic | 22.9 | 66 | -24.8 FAIL | +0.05 pass | -61.4 pass | +0.001 pass |
| synthetic | 22.9 | 99 | -24.4 FAIL | +0.07 pass | -62.5 pass | +0.001 pass |
| synthetic | 25.4 | 33 | -25.3 pass | -0.06 pass | -61.5 pass | +0.001 pass |
| synthetic | 25.4 | 66 | -25.3 pass | -0.05 pass | -62.0 pass | +0.001 pass |
| synthetic | 25.4 | 99 | -24.9 FAIL | -0.05 pass | -63.0 pass | +0.001 pass |

### Summary

| | M1 | M2 | M3 (costliest trial) | Accepted |
| --- | --- | --- | --- | --- |
| R1 | 3/36 | 26/36 | 0.07 s | no |
| R2 | 36/36 | 36/36 | over 120 s in all three runs | no |

M3 on a standard GitHub runner (official, Experiments workflow, 2026-11-27): R1 0.1 s
median; R2 over the 120 s budget in all three runs, as on the development machine.

### Predictions against outcomes

| Prediction (recorded 2026-11-18) | Outcome |
| --- | --- |
| R1 fails M1 and M2 for the 5.1 cm disc at every distance and for the 9.0 cm disc at 66 and 99 cm, with both clicks | **M2: confirmed exactly** (those 10 combinations fail, all others pass). **M1: refuted in scope**: R1 fails M1 in 33 of 36 combinations, not only these, passing only for the two largest discs with the synthetic click, by 0.3 to 0.4 dB |
| ...and passes the rest | Refuted for M1 (see above); confirmed for M2 |
| R2 passes M1 and M2 for all 36 combinations | Confirmed: M1 from -40.2 to -63.0 dB, M2 within 0.006 dB |
| R2 passes M3 with the synthetic click; recorded click not predicted | Not testable as registered: M3 measures only the costliest combination, which uses the recorded click. There, all three runs exceeded the budget |

**Why R1 fails M1 so widely.** Diffraction of order two and above sits 20 to 32 dB below
the echo (EXP-0004). That is too weak to move a band level by 1 dB, which is why R1 passes
M2 for the larger discs, but strong enough to fail a spectral accuracy of -25 dB. The two
metrics measure different things, and both were registered.

## Conclusion (2026-11-27)

Neither candidate passes every gate. Decision rule 3 applies: R2, which passes M1 in all
36 combinations (R1: 3), renders the exercises. No trial fails M1 or M2 with R2, so none
needs wave-solver echoes. The failed gate, cost with a broadband click, is the next
problem. What makes it costly is solving C2 per trial at every frequency where a sharp
click has energy, up to 21.6 kHz; but those frequency responses depend only on the disc
and its distance, not on the click. A renderer that computes them once per disc and
reuses them for every click and trial is the natural next candidate.

R1, contributed by Kimi, remains the fastest renderer by three orders of magnitude, and
the exercise code's structure (report, own-click substitution, screen-reader text) comes
from it.
