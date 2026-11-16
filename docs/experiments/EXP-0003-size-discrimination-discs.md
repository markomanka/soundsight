# EXP-0003: echoes of the size-discrimination discs

Status: **pre-registered 2026-11-15; not run.** Results will be added below the
protocol, which will not be rewritten.

## Question

Can the production engine (geometric acoustics with edge diffraction, decision 2)
reproduce the echo levels of the discs used in the size-discrimination task of the
training study we take as our template (literature A3), over the distances that task
uses?

## Why this workload

It replaces invented test sizes with the stimuli of a published, validated training
task. Literature A3 used a 25.4 cm reference disc against comparison discs of 5.1, 9.0,
13.5, 17.5 and 22.9 cm diameter, starting at 33 cm and moving 33 cm further after two
sessions at 90% correct; experts worked at 100 cm. Literature B2 measured detection of a
17.5 cm disc at 100 cm.

## Workload (fixed)

- Six rigid discs of diameter 5.1, 9.0, 13.5, 17.5, 22.9 and 25.4 cm.
- Three distances: 33, 66 and 99 cm. Eighteen cases.
- Each disc faces the listener, centred straight ahead; source and receiver coincide.
- Simplifications, stated so they are not mistaken for the real task: the study's discs
  were foam board on a pole, two at a time, above and below ear height.

## Reference (fixed)

The wave solver of `soundsight.acoustics.reference.fdtd`, at 12 or more cells per disc
radius and 10 or more cells per wavelength at 4 kHz, with the sub-cell edge correction.

## Metrics and thresholds (fixed)

1. **Level.** For each of the 18 cases, echo level over 2 to 4 kHz within **1.0 dB** of
   the reference.
2. **Size cue.** At each distance, the level difference between the reference disc and
   each comparison disc within **1.5 dB** of the reference's difference. Fifteen pairs.
3. **Decision rule.** The engine is used in exercises only for cases that pass both.
   For a failing case the exercise uses responses precomputed with the wave solver, and
   the failure is recorded in the conformance matrix.

## Predictions, recorded before running

- The 5.1 cm disc will fail metric 1 with first-order edge diffraction at all three
  distances: over the click band its ka runs from 0.9 to 1.9, inside or just above the
  gap found in EXP-0002.
- Discs of 13.5 cm and larger will pass at 66 and 99 cm.
- At 33 cm the larger discs subtend a wide angle (radius up to 0.38 of the distance), so
  waves crossing the disc from rim to rim will be strong; whether first-order
  diffraction passes there is not predicted.

## Results

Not yet run. The engine it tests does not exist yet; the reference values may be
computed at any time, but no threshold above may change once they are.
