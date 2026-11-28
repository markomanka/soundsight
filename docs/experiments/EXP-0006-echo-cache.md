# EXP-0006: exercise trials from a per-disc echo cache

Status: pre-registered 2026-11-27 (published on GitHub before any measurement); run
2026-11-27 to 28. **Concluded: R3 passes every gate and renders exercises.** Results are
below the protocol, which has not been rewritten.

## Question

Can a cache of each disc's echo, computed once and reused for every click and trial,
render exercise trials with the accuracy of diffraction of all orders at a cost that fits
an exercise pack?

## Why

EXP-0005 chose R2, which matches diffraction of all orders in all 36 combinations of its
workload, but a trial with a sharp click exceeded the 120 s budget: R2 solves the
all-orders equation per trial, at every frequency where the click has energy. Those
solutions depend only on the disc and its distance, not on the click.

## Candidate R3

`soundsight.exercise.render_cached`, frozen with this protocol. For each disc it solves
diffraction of order two and above once, at frequencies from zero to 0.45 times the
sample rate spaced 100 Hz apart, and stores them relative to the mirror echo's arrival.
A trial's impulse response is R1's first-order response plus that cached response over a
10 ms window starting at the mirror echo; the click is then convolved as in R1 and R2.

Two design choices were made before freezing, on a disc outside the workload (20 cm at
50 cm, 16 kHz):

- **The 10 ms window.** All higher-order paths are longer than the mirror path, so they
  arrive after it. Compared with a 40 ms window, a 10 ms one differs by -26.6 dB of the
  higher orders, which are themselves about 24 dB below the echo: about -50 dB of the
  echo, against M1's -25 dB.
- **The zero-frequency term is solved.** Left out, the same comparison was -18.4 dB:
  higher orders largely cancel first order at long wavelengths, and a missing
  zero-frequency term spreads an offset across the window. Solving it required a fix in
  the banded all-orders solver, whose lowest band excluded zero; EXP-0005 never used zero
  frequency, so its results are unaffected.

## Workload, reference and accuracy metrics (fixed)

Identical to EXP-0005, reused from its runner unchanged: the 18 discs of the
size-discrimination task, each with the synthetic and the recorded click (36
combinations); C2 at 200 logarithmically spaced frequencies from 250 Hz to 20 kHz and at
the 41 click-band frequencies.

- **M1:** click-weighted error against C2 at most **-25 dB**.
- **M2:** echo level from 2 to 4 kHz within **1.0 dB** of C2.

## Cost (fixed)

- **M3a, a trial from the cache:** median of three renders of the costliest combination
  (25.4 cm at 33 cm, recorded click), cache already built: at most **1 s**.
- **M3b, building a cache:** one fresh build for the costliest disc (25.4 cm at 33 cm): at
  most **1,200 s**. Eighteen discs then take at most six hours, so a pack precomputes
  overnight.

Official figures come from a standard GitHub ubuntu-24.04 runner, as notices of the
Experiments workflow; a build exceeding its budget is stopped there.

Thresholds are in `docs/quality/budgets.toml` under `experiments.exp0006`.

## Decision rule (fixed)

1. R3 is accepted if it passes M1 and M2 in all 36 combinations, M3a and M3b.
2. If accepted, R3 renders exercises; R2 remains the reference implementation that R3 is
   checked against.
3. If not, R2 keeps rendering exercises, and the failed gate is recorded as the next
   problem.

## Predictions (recorded 2026-11-27)

- R3 passes M1 and M2 in all 36 combinations, with M1 below -35 dB everywhere.
- M3a passes, below 0.2 s.
- M3b passes: building the costliest disc's cache takes about 7 minutes on the development
  machine (about 217 frequencies, half of them in the most expensive octave).

## How to run

```
uv run python tools/fetch_legacy_click.py
uv run python tools/experiments/exp0006.py build --time-limit 250   # repeat until done
uv run python tools/experiments/exp0006.py run
uv run python tools/experiments/exp0006.py cost
```

## Results (2026-11-28)

R3 as frozen in the registration (merged to `main` before any measurement; the code run
was checked to be identical). The references are EXP-0005's, reused unchanged. Every
number is stored in `EXP-0006-results.json`; the Experiments workflow recomputes three
combinations from scratch and measures M3a and M3b on a standard GitHub runner.

### M1 and M2 per combination

| Click | Diameter (cm) | Distance (cm) | R3 M1 (dB) | R3 M2 (dB) | R2 M1 for comparison (dB) |
| --- | --- | --- | --- | --- | --- |
| recorded | 5.1 | 33 | -43.6 | -0.0156 | -40.2 |
| recorded | 5.1 | 66 | -61.5 | +0.0007 | -41.3 |
| recorded | 5.1 | 99 | -38.8 | -0.0345 | -42.8 |
| recorded | 9.0 | 33 | -68.9 | +0.0012 | -48.7 |
| recorded | 9.0 | 66 | -66.2 | +0.0010 | -49.6 |
| recorded | 9.0 | 99 | -62.2 | +0.0016 | -51.1 |
| recorded | 13.5 | 33 | -65.3 | +0.0026 | -50.9 |
| recorded | 13.5 | 66 | -70.0 | +0.0017 | -51.8 |
| recorded | 13.5 | 99 | -62.1 | +0.0001 | -53.3 |
| recorded | 17.5 | 33 | -72.9 | +0.0004 | -52.8 |
| recorded | 17.5 | 66 | -74.9 | +0.0009 | -53.9 |
| recorded | 17.5 | 99 | -73.2 | +0.0004 | -55.2 |
| recorded | 22.9 | 33 | -75.9 | +0.0003 | -54.9 |
| recorded | 22.9 | 66 | -71.9 | -0.0001 | -56.3 |
| recorded | 22.9 | 99 | -74.9 | +0.0010 | -57.7 |
| recorded | 25.4 | 33 | -76.8 | +0.0011 | -55.3 |
| recorded | 25.4 | 66 | -75.6 | +0.0003 | -56.8 |
| recorded | 25.4 | 99 | -78.0 | +0.0007 | -58.3 |
| synthetic | 5.1 | 33 | -44.2 | -0.0156 | -43.9 |
| synthetic | 5.1 | 66 | -62.6 | +0.0007 | -45.0 |
| synthetic | 5.1 | 99 | -39.5 | -0.0345 | -48.1 |
| synthetic | 9.0 | 33 | -69.9 | +0.0012 | -53.4 |
| synthetic | 9.0 | 66 | -67.2 | +0.0010 | -53.9 |
| synthetic | 9.0 | 99 | -63.0 | +0.0016 | -56.2 |
| synthetic | 13.5 | 33 | -65.3 | +0.0026 | -58.2 |
| synthetic | 13.5 | 66 | -69.6 | +0.0017 | -55.8 |
| synthetic | 13.5 | 99 | -62.0 | +0.0001 | -57.2 |
| synthetic | 17.5 | 33 | -74.6 | +0.0004 | -61.6 |
| synthetic | 17.5 | 66 | -75.2 | +0.0009 | -58.6 |
| synthetic | 17.5 | 99 | -73.7 | +0.0004 | -59.9 |
| synthetic | 22.9 | 33 | -78.4 | +0.0003 | -62.3 |
| synthetic | 22.9 | 66 | -73.2 | -0.0001 | -61.4 |
| synthetic | 22.9 | 99 | -75.2 | +0.0010 | -62.5 |
| synthetic | 25.4 | 33 | -77.3 | +0.0011 | -61.5 |
| synthetic | 25.4 | 66 | -77.4 | +0.0003 | -62.0 |
| synthetic | 25.4 | 99 | -78.1 | +0.0007 | -63.0 |

All 36 pass both gates: M1 from -38.8 to -78.4 dB, M2 within 0.035 dB.

### Cost

| Gate | Development machine | Budget | Verdict |
| --- | --- | --- | --- |
| M3a, a trial from the cache (median of 3, costliest combination) | 57 ms | 1 s | pass |
| M3b, building the costliest disc's cache | 371 s | 1,200 s | pass |

M3b on the development machine is the compute time of the resumable build, summed over
its chunks, which slightly overstates a single uninterrupted build. Building all 18 discs
took 34 minutes. On a standard GitHub runner (official, Experiments workflow,
2026-11-28, two runs): cache build 274 s and 281 s, trial from cache 0.05 s.

### Predictions against outcomes

| Prediction (recorded 2026-11-27) | Outcome |
| --- | --- |
| R3 passes M1 and M2 in all 36 combinations, with M1 below -35 dB everywhere | Confirmed: worst M1 -38.8 dB (5.1 cm disc at 99 cm, recorded click) |
| M3a passes, below 0.2 s | Confirmed: 57 ms |
| M3b passes, about 7 minutes on the development machine | Confirmed: 6.2 minutes |

**R3 against R2.** R3 is not uniformly more accurate than R2: relative to R2's M1, it is
between 21.6 dB better and 8.6 dB worse, depending on the combination. Its window drops
the higher orders after 10 ms, while R2 solves only where the click has energy. Both are
far inside the gate, and R3 costs a thousandth as much per trial once its disc is cached.

## Conclusion (2026-11-28)

R3 passes M1 and M2 in all 36 combinations, and M3a and M3b. By decision rule 2, R3
renders exercises. R2 remains the reference implementation that R3 is checked against.
An exercise pack for the size-discrimination task needs 18 disc caches (about half an
hour on the development machine) and then renders any trial, with any click, in about a
twentieth of a second.
