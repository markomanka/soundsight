# EXP-0006: exercise trials from a per-disc echo cache

Status: **pre-registered 2026-11-27.** Protocol, thresholds and candidate R3 are fixed and
published before any measurement. Results will be added below the protocol, which will
not be rewritten.

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

## Results

Not yet run.
