# How the acoustics is validated

Every acoustic model in SoundSight is checked against a ladder of references, each rung
resting on the one below. The checks run in continuous integration on every change.
The reasoning behind the choice of engine is in
[decision 2](../decisions/0002-acoustic-engine.md).

## Conventions

- **Monostatic.** Source and receiver are at the same point: a first-order model of a
  person hearing the echo of their own click.
- **Unit point source.** It radiates `exp(-ikr) / r` in free field. Time dependence is
  `exp(+i omega t)`, as in numpy's FFT, so a delay multiplies a spectrum by
  `exp(-i omega tau)`.
- **Echo ratio.** The echo of an object divided by the echo of an infinite rigid wall at
  the distance of the object's nearest point. It has no units: 1 means "echoes like a
  wall".
- **Band level.** `10 log10(mean |echo ratio|^2)` over the click band, 2 to 4 kHz, in
  decibels relative to a wall. Acceptance thresholds use this unit because about 1 dB is
  the smallest level difference listeners notice.
- **ka.** Size in wavelengths: 2 pi times radius over wavelength. Linear acoustics
  depends only on sizes in wavelengths (a property test checks this), which is why a
  test at a cheap scale still binds at echolocation frequencies.

## The ladder

### Rung 0: exact solutions (`soundsight.acoustics.reference.analytic`)

| Solution | Checked against |
| --- | --- |
| Free field and rigid wall (image source) | Definition |
| Rigid sphere, exact partial-wave series | Rayleigh's long-wavelength limit (within 0.3%), the geometrical-reflection limit (within 0.3%), independence from the convergence tolerance, Bessel recurrences against SciPy and against asymptotic forms at orders where ordinary functions overflow |
| Compact sphere and compact disk (long-wavelength limits) | The exact sphere series at five distances (within 0.3%) |

Two further closed forms are *approximations* and are labelled as such: the Kirchhoff
disk and the disk with first-order edge diffraction.

### Rung 1: the wave solver (`soundsight.acoustics.reference.fdtd`)

An axisymmetric finite-difference time-domain solver for scenes that are rotationally
symmetric about the line from the listener through the object. It is trusted because of
these tests, not because of its code:

| Property | Result |
| --- | --- |
| Amplitude falls as 1/distance | Within 0.1% |
| Phase error falls 4 times when the cell size is halved | Second-order accuracy, as theory requires |
| Echo ratio of a wall | 1 to within 1e-6 |
| Discrete energy in a rigid box | Constant to 1e-9 over more than 1000 steps |
| Sphere against the exact series, ka up to 3 | Error 21%, 7%, 4% at 8, 16, 32 cells per radius: the staircase error shrinks steadily |
| Small disk against the exact long-wavelength limit | Within 3% at 8 cells per radius and 2% at 16 |
| Disk echo level, coarse grid against fine grid | Within 0.3 dB |
| Model error for a disk of 5 cm radius, at 6, 12 and 18 cells per radius | -0.56, -0.78 and -0.81 dB: converged by 12 cells, which is now the minimum for every reference used to judge a model |

Two properties of the solver are recorded because they affect how it may be used.

- **Sub-cell edge position.** A thin disk drawn `n` cells wide scatters like a disk of
  radius `(n + 0.35)` cells. The constant `DISK_EDGE_OFFSET_CELLS` is calibrated against
  the exact long-wavelength limit and pinned by tests at two resolutions.
- **Staircased spheres.** A sphere is built from cells, so its error grows with
  frequency. It is used to check the solver only up to ka = 3; the disk, which lies on
  the grid, is the reference object.

To cancel numerical dispersion, the echo ratio is formed from two signals that travelled
the same distance through the same grid: the scattered pulse at the listener and the
free-field pulse at twice the object's distance.

### Rung 2: the conformance matrix (`tests/acoustics/test_conformance.py`)

Candidate models are run through canonical problems whose reference comes from rung 0
or rung 1. Each pair has a declared verdict.

| Canonical problem | Reference | Tolerance |
| --- | --- | --- |
| Wall | Exact | Exactly 1 |
| Disk of 5 cm and of 10 cm at 1 m, level in the click band | Wave solver | 1.0 dB |
| Size cue between those disks | Wave solver (+10.6 dB) | 1.5 dB |
| Large disk, complex spectrum for ka above 5 | Wave solver | 8% mean error |
| Small disk, complex spectrum for ka below 0.5 | Wave solver | 5% mean error |
| Disk in the gap between the models, level for ka 1.0 to 1.5 | Wave solver | 1.0 dB (no current model passes) |
| Sphere, level for ka 0.1 to 0.3 and for ka 40 to 80 | Exact series | 1.0 dB |

A pair declared FAIL is a strict expected failure: the test reports the measured error
and breaks if the model unexpectedly passes, so the record is corrected deliberately.

### Rung 3: the production engine

`soundsight.acoustics.engine` is admitted like any other model, through the conformance
matrix, and in addition is tested for laws that hold for every scene (continuity at
reflection boundaries, reciprocity, scale invariance, the wall limit, convergence and
impulse-response fidelity). See [the engine](engine.md) and the pre-registered
[EXP-0003](../experiments/EXP-0003-size-discrimination-discs.md), which a separate CI
workflow re-runs weekly and on every change to the acoustics code.

## Admitting a new engine

1. Wrap it in a class with a `name` and an `echo_ratio(target, frequency_hz)` method
   (the `EchoModel` protocol in `soundsight.acoustics.canonical`).
2. Add it to `MODELS` in `tests/acoustics/test_conformance.py`.
3. Declare a verdict for every canonical problem it claims to handle.
4. Use it only within the range where it passes, and state that range in its
   documentation.

New kinds of scene need a new canonical problem with a reference from rung 0 or 1 before
any engine is trusted on them.

## Running the checks

```
uv run pytest tests/acoustics           # everyday checks, about 10 seconds
uv run pytest tests/acoustics -m slow   # fine grids, about 1 minute
```

## Known limits of the validation itself

All references here are theory and simulation. They agree with each other, but none has
yet been compared with recordings of real echoes. Until measured binaural impulse
responses are added as a further rung, "validated" means "consistent with the physics of
ideal rigid objects", not "indistinguishable from reality".
