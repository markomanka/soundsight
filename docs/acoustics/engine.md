# The acoustic engine

The production engine chosen in [decision 2](../decisions/0002-acoustic-engine.md):
geometric acoustics with edge diffraction. This page states what the current increment
computes, how it is checked and where it may be used. Code:
`soundsight.acoustics.engine`. Literature identifiers refer to
[docs/research/literature.md](../research/literature.md).

## Increment 1: one thin rigid plate (2026-11-16)

For a convex, planar, rigid plate of zero thickness, a point source and a point receiver
(the same point for a person hearing their own click), the echo is:

- **the specular reflection**, by the image-source method, when the reflection point
  lies on the plate; with half weight when it lies exactly on an edge;
- **first-order edge diffraction** from every edge, by the Biot-Tolstoy-Medwin
  secondary-source formulation (H1), which is exact for a rigid wedge and was validated
  for room acoustics by H2.

The result is a list of arrivals, each a delay and an amplitude. From it the engine gives
the frequency response exactly, or an impulse response at any sample rate, by placing a
windowed-sinc fractional delay at each arrival. A 17.5 cm disc at 1 m takes about 20 ms
for the arrivals and 0.2 s for a 48 kHz impulse response.

Two numerical safeguards matter for correctness, and both are tested:

- Near a reflection boundary the diffraction integrand becomes a narrow peak. The
  quadrature is graded geometrically towards it, and two quantities that would otherwise
  lose all precision to cancellation are computed in rewritten forms. Without these the
  field showed a spurious step of 1e-4 at a micrometre from the boundary and failed
  outright at a nanometre.
- The uniform quadrature step follows the phase at the highest frequency requested.

## How it is checked

| Property | Test result |
| --- | --- |
| Continuity where the reflection point crosses an edge | The step across the boundary equals slope times distance at every scale down to 0.1 micrometre; on the boundary the field equals the mean of both sides to 1e-15 |
| Reciprocity (swap source and receiver) | Equal to rounding, for random positions (property test) |
| Only sizes in wavelengths matter | Scaling the scene by s and frequency by 1/s scales the echo by exactly 1/s (property test) |
| A large plate echoes like a wall | Deviation falls from 0.26 to 0.006 as the plate grows from 2 m to 32 m across |
| Quadrature converged | Doubling its density changes the result by less than 1e-9 |
| Disk polygons converge | Second order: each doubling of sides reduces the difference four times |
| Impulse response | Its spectrum matches the exact frequency response within 2e-4 up to 0.45 times the sample rate; nothing arrives early |
| Agreement with theory | For a disk straight ahead it reproduces the closed form with the exact rim coefficient within 2e-3; the two derivations share no code |
| Agreement with the wave solver | The conformance matrix and EXP-0003, below |

## Where it may be used

From the conformance matrix ([validation](validation.md)) and the pre-registered
experiment [EXP-0003](../experiments/EXP-0003-size-discrimination-discs.md):

- **Valid (within 1 dB of the wave solver):** discs of 13.5 cm diameter and larger at
  33 to 99 cm, and the 9.0 cm disc at 33 cm. In the size-discrimination task, 10 of 15
  trials can use the engine.
- **Not valid:** discs of 5.1 cm diameter (1.9 to 2.0 dB too loud) and, narrowly, 9.0 cm
  at 66 and 99 cm (1.1 dB too quiet). These objects are only one or two wavelengths around, so a
  wave crosses them rim to rim several times; first-order diffraction leaves this out.
  Their echoes are precomputed with the wave solver, as the protocol requires.

## Next increments

1. **Higher-order diffraction** for small objects, chosen by the pre-registered
   [EXP-0004](../experiments/EXP-0004-higher-order-diffraction.md) between explicit
   second-order diffraction and the edge-source integral equation of H3, which handles
   all orders and agrees with reference solutions for a circular disc across the whole
   frequency range.
2. **Several objects, with occlusion.** The current API takes one plate on purpose:
   summing plates without visibility tests would give wrong answers silently.
3. Rigid boxes (wedges of 270 degrees), absorbing surfaces, rooms, and two ears.

Each increment comes with a canonical problem and a reference before the engine is
trusted on it.
