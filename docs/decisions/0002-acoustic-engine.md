# 2. Acoustic engine: rays with edge diffraction in production, waves as the referee

Date: 2026-11-15. Status: accepted. Implementation: increment 1 (one thin plate,
first-order diffraction) since 2026-11-16, see [the engine](../acoustics/engine.md). Evidence: `tests/acoustics/`, described in
[docs/acoustics/validation.md](../acoustics/validation.md).

Literature: A3, B1, B2, D3, D5, H1, H2, H3 (see [docs/research/literature.md](../research/literature.md)).
Experiments: EXP-0002 (retrospective evidence), EXP-0003 (pre-registered, run 2026-11-16), EXP-0004 (pre-registered: which higher-order diffraction).

## Context

The 2016 demonstrator computed echoes with GSound, a closed third-party library that
traces rays ("beams") through the scene and sums their energy in four frequency bands.
Nobody on the project could inspect it, fix it or say where its answers stopped being
right. Replacing it raises two questions: which physics to compute, waves or rays, and
how to make sure the replacement can never again be a black box.

## What the listener needs from the physics

A tongue click carries most of its energy between 2 and 4 kHz, where the wavelength is
9 to 17 cm. The objects of echolocation training (a pole, a disk, a doorway, a person)
are between a fraction of a wavelength and a few wavelengths across, at 0.3 to 5 m.

Two quantities decide which physics applies.

- **Size in wavelengths.** Written `ka` (2 pi times radius over wavelength). At 3 kHz a
  5 cm disk has ka = 2.7 and a 20 cm disk ka = 11.
- **The Fresnel zone.** A surface reflects like a mirror only if it covers the first
  Fresnel zone around the reflection point, of radius sqrt(wavelength x distance / 2):
  24 cm at 3 kHz and 1 m. Anything smaller returns an echo whose strength depends on its
  size and on frequency.

Most training targets are therefore *below* the mirror regime, and that is not a
nuisance: the size- and frequency-dependence of the echo is the cue the trainee learns.
Our wave solver finds that doubling a disk's radius from 5 to 10 cm at 1 m raises its
echo by 10.6 dB.

## Options

### A. Solve the wave equation (finite differences, finite or boundary elements)

Correct for every effect, including diffraction, at every size. But the cost grows with
the volume of air and the fourth power of the highest frequency. For a small room
(4 x 5 x 2.5 m) up to 8 kHz, a standard scheme needs about 6 x 10^8 cells and 7,000 time
steps to cover 50 ms: roughly 4 x 10^12 cell updates, on the order of an hour on a good
GPU. That is for **one** listener position, and in echolocation the source moves with
the listener, so every position and every step of a walk is a new simulation. A coarse
grid of 400 positions would take weeks; a phone could not do one. Doubling the top
frequency multiplies everything by 16. (Order-of-magnitude estimates: 10 cells per
wavelength, 10^9 cell updates per second.)

### B. Rays or beams with mirror reflections only

Fast, independent of frequency, and naturally gives each echo's delay and direction,
which is what binaural rendering needs. But a mirror reflection does not know how big
the mirror is. Measured against the wave solver (click band, 1 m):

- a 5 cm disk comes out 15.8 dB too loud and a 10 cm disk 5.1 dB too loud;
- the size cue between them is 0 dB instead of 10.6 dB;
- a small sphere (ka 0.1 to 0.3) comes out 22.6 dB too loud.

A trainee could not learn size, and would learn to expect echoes from objects that
return almost none. Coarse frequency bands (GSound used four, with nearly all of a
click's energy in one of them) blur what frequency dependence remains.

### C. Rays plus edge diffraction, computed as impulse responses, with a wave solver as referee

Keep the path-based engine of B, but add the wave physics it lacks in the form of
diffraction from edges, with the exact coefficient for a rigid edge, and treat objects
much smaller than the wavelength with the closed-form long-wavelength (Rayleigh)
solution. Compute impulse responses in the time domain, so phase is kept and any click,
including the user's own, can be played through them.

Measured against the wave solver:

| Canonical problem | Mirror only | Kirchhoff | Edge diffraction (first order) | Compact (Rayleigh) |
| --- | --- | --- | --- | --- |
| 5 cm disk at 1 m, level in click band | +15.7 dB | -1.4 dB | -0.7 dB | +0.7 dB |
| 10 cm disk at 1 m, level in click band | +5.1 dB | -0.1 dB | +0.4 dB | +8.2 dB |
| Size cue, 5 to 10 cm (wave solver: +10.6 dB) | 0.0 dB | +11.9 dB | +11.8 dB | +18.1 dB |
| Large disk (ka 5 to 12), complex spectrum error | not applicable | 17% | 6% | not applicable |
| Small disk (ka below 0.5), complex spectrum error | not applicable | not tested | above 50% | below 5% |
| Disk in the gap (ka 1.0 to 1.5), level | not tested | +2.3 dB | +4.5 dB | -2.7 dB |
| Small sphere (ka 0.1 to 0.3), level vs exact | +22.6 dB | not applicable | not applicable | +0.2 dB |
| Large sphere (ka 40 to 80), level vs exact | 0.0 dB | not applicable | not applicable | wrong by design |

Level errors are relative to the reference; about 1 dB is the smallest difference a
listener notices. "5 cm" and "10 cm" are radii. Numbers revised on 2026-11-17 after two
corrections to how references are computed (12 cells per radius instead of 6; band
levels at fixed frequencies instead of FFT bins); no conclusion of this decision changed. "Kirchhoff" is the classic textbook approximation; it is included to
show that the *correct* edge coefficient matters: its rim wave is too weak whenever the
listener is not in the mirror direction of the rim, by a quarter for a disk whose radius
is 0.3 of its distance.

### What the literature adds

- The size-discrimination task of the training study we take as a template (A3) uses
  discs of 5.1 to 25.4 cm diameter at 33 to 99 cm: all smaller than the Fresnel zone, so
  the task *is* the size-dependence that mirror reflection lacks. Its smallest disc has
  ka between 0.9 and 1.9 over the click band, inside the gap described below.
- Expert listeners detect echoes 27 dB below the emission (B2), so an engine may not
  discard weak echoes as negligible.
- A round robin of room-acoustics software against measurements found that the programs
  could not give a reliable pattern of early reflections, largely because diffraction
  was missing or insufficient, and that simulated and measured responses were always
  audibly different (D5). Predicting room parameters to within a just-noticeable
  difference needs input data better than exists (D3). Both point the same way as our
  measurements: early reflections with correct diffraction are the hard and necessary
  part, and claims of accuracy must be made problem by problem.

## Decision

1. **Production engine: geometric acoustics with edge diffraction (option C).** Paths
   are found with image sources; edges contribute diffracted impulse responses
   (Biot-Tolstoy-Medwin formulation, exact for a rigid wedge); objects much smaller than
   the wavelength use the compact-scatterer closed form. Output is a time-domain impulse
   response per path, with the direction of departure and arrival.
2. **Waves are the referee, not the product.** A small wave solver, itself validated
   against exact solutions, provides reference answers where no formula exists. It runs
   in CI in seconds because the canonical scenes are rotationally symmetric and because
   linear acoustics depends only on sizes in wavelengths, so tests can run at whatever
   scale is cheapest.
3. **An engine is defined by the problems it answers, not by its code.** Any engine,
   present or future, is wrapped as an `EchoModel` and run through the conformance
   matrix in `tests/acoustics/test_conformance.py`. Each (model, problem) pair has a
   declared verdict; expected failures are strict, so the record cannot drift from the
   behaviour in either direction. An engine is used only inside the range where it
   passes.

## Consequences

- No black box: every claim about the engine is a test that runs on each change.
- Swapping engines is routine: a new one needs an adapter and its declared verdicts.
- The cost of an echo is independent of frequency and small enough for interactive use
  and, later, phones.
- Each approximation has a stated, tested range. For a rigid disk facing the listener:
  the compact model is within 5% below ka = 0.5; first-order edge diffraction is within
  1 dB over the click band from about ka = 2 upward and improves with size; mirror
  reflection alone is valid only for surfaces larger than the Fresnel zone and for large
  convex bodies.
- **There is a known gap.** Between about ka = 0.75 and 1.5 neither simple model reaches
  1 dB (over ka 1.0 to 1.5 the compact model is 2.7 dB low, first-order edge diffraction
  4.5 dB high), and just above it first-order diffraction still wobbles by up to 2 dB in narrow
  bands. At 3 kHz, ka = 1 is a radius of 1.8 cm, so this is the regime of thin poles. It
  will need higher-order diffraction or scattering tables precomputed with the wave
  solver. The conformance matrix records the gap, so closing it is a visible event.

## What this decision does not settle

- The general engine is not written yet. The "edge diffraction" entry above is a
  closed form for one geometry (a disk facing the listener), standing in for what the
  engine must reproduce. Implementing image sources and edge diffraction for arbitrary
  polyhedral scenes against this suite is the next step.
- Only rigid objects straight ahead are covered. Absorbing and rough surfaces, curved
  bodies such as poles and people, objects off axis, rooms, and two ears with a head
  between them each need canonical problems of their own.
- Waves that cross an object from edge to edge (higher-order diffraction) are left out
  of the first-order model; they account for most of its remaining 6% error.
- Theory and simulation agree with each other; neither has yet been compared with
  recordings of real echoes. That comparison, with measured binaural impulse responses,
  is the validation that matters most and is planned with the academic partners.

## When to revisit

If measurements of real echoes disagree with both the engine and the wave solver; if
target hardware makes option A affordable for interactive use; or if a class of scene
that matters for training cannot be brought within 1 dB by option C.
