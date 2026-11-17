# EXP-0004: which higher-order edge diffraction closes the gap?

Status: **pre-registered 2026-11-17.** Protocol, references and baseline measurement are
fixed; no candidate exists yet. Results will be added below the protocol, which will not
be rewritten.

## Question

Which formulation of higher-order edge diffraction brings the echoes of objects one to two
wavelengths around within the perceptual tolerances, at a cost that allows exercises to be
precomputed?

## Why

Engine increment 1 (first-order diffraction) fails for the 5.1 cm disc at every distance
and for the 9.0 cm disc at 66 and 99 cm (EXP-0003). These discs are one or two
wavelengths around over the click band, so a wave crosses them rim to rim several times;
first-order diffraction leaves this out. Literature H2 found second-order diffraction
often negligible in rooms; EXP-0003 found the exception that matters to echolocation.

## Candidates

| ID | Formulation | Expected cost |
| --- | --- | --- |
| C0 | Baseline: engine increment 1, first order only. Measured at registration, below. | Lowest |
| C1 | First- plus second-order edge diffraction: explicit edge-to-edge paths of secondary sources, extending H1. Time domain, like increment 1. | Grows with the square of the number of edge points |
| C2 | Edge-source integral equation, all orders (H3), solved in the frequency domain on pairs of edge points; first-order diffraction may take over above a crossover frequency only if the candidate's own convergence test shows the higher orders below -40 dB of the echo there. | A dense linear solve per frequency |

## Workloads and references (fixed)

- **W1. EXP-0003, re-run unchanged** (with its corrected level metric). Acceptance: all 18
  levels within 1.0 dB and all 15 size cues within 1.5 dB.
- **W2. A disc across the gap.** Radius 10 cm, distance 0.77 m (radius 0.13 of the
  distance), four bands of ka: 0.25 to 0.5, 0.5 to 1, 1 to 2 and 2 to 4, each at 12 fixed
  values. Reference: the wave solver at 16 cells per radius, in two runs excited around
  ka 0.6 and ka 2. Acceptance in **every** band: echo level within **1.0 dB** and mean
  complex spectrum error at most **10%**.
- **W3. Physical laws.** The engine test suite (continuity at reflection boundaries,
  reciprocity, scale invariance, wall limit, convergence, impulse-response fidelity)
  passes unchanged.
- **W4. Cost**, on a standard GitHub ubuntu-24.04 runner, median of three runs, for the
  25.4 cm disc at 33 cm: (a) frequency response at 20 frequencies between 2 and 4 kHz in
  at most **10 s**; (b) a full 48 kHz impulse response in at most **120 s**. Reason: an
  exercise pack of about 200 echoes should precompute overnight on modest hardware.

Thresholds are in `docs/quality/budgets.toml` under `experiments.exp0004`.

### Validity of the reference (checked at registration and by CI)

- The two runs agree where both are excited (ka 1.0 to 1.3) within 0.3 dB. Measured:
  +0.001 dB; largest pointwise difference 0.07%.
- At ka 0.25 the reference approaches the exact long-wavelength limit for a small rigid
  disk within 3%. Measured: 1.1%.

Preparing these checks exposed a defect in the level metric of EXP-0003 (averages over
FFT bins); it was corrected there, by a dated amendment, before this protocol was fixed.

## Baseline (C0), measured at registration

| ka band | Reference (dB) | C0 (dB) | Level error (dB) | Spectrum error | Verdict |
| --- | --- | --- | --- | --- | --- |
| 0.25 to 0.5 | -40.69 | -17.71 | +22.98 | 1591% | FAIL |
| 0.5 to 1.0 | -28.40 | -16.07 | +12.33 | 425% | FAIL |
| 1.0 to 2.0 | -13.98 | -12.53 | +1.45 | 91% | FAIL |
| 2.0 to 4.0 | -7.12 | -7.48 | -0.36 | 17% | FAIL |

Levels relative to a wall at the disc's distance.

## Decision rule (fixed)

1. A candidate is accepted if it passes W1, W2, W3 and W4.
2. Of the accepted candidates, the one with the lower W4(b) cost becomes engine
   increment 2; on a tie within 20%, C1, because it is simpler.
3. If no candidate is accepted, the one that passes W3 and the most W1 cases is
   implemented, the failing cases keep their wave-solver echoes, and the failed gates are
   recorded as the next problem.

## Predictions (recorded 2026-11-17)

- C1 brings the 9.0 cm disc within tolerance at all distances but not the 5.1 cm disc,
  and fails W2 below ka 1.
- C2 passes W1 and W2.
- C2 meets W4(a); whether it meets W4(b) depends on how many frequencies need the full
  solve, and is not predicted.

## How to run

```
uv run python tools/experiments/exp0004.py --check   # reference validity and baseline
uv run python tools/experiments/exp0003.py --check   # W1 for the current engine
```

Candidate evaluation will be added to `tools/experiments/exp0004.py` unchanged in its
metrics: each candidate is wrapped as an `EchoModel` and passed to the same functions that
measured the baseline.

## Results

Not yet run: no candidate exists.
