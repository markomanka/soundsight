# Roadmap

The plan of record. Each stage has exit gates in
[docs/quality/quality-gates.md](quality/quality-gates.md); a stage is finished when its
gates are met, not when its code exists. Literature identifiers (A3, B1, ...) refer to
[docs/research/literature.md](research/literature.md).

The staging merges the plan agreed at the project's restart with the stage-gate
structure proposed by Kimi (kimi.ai) on 2026-11-15.

## Premise, and what is not yet known

Click-based echolocation can be learned by blind and sighted adults of any age in about
ten weeks, with reported gains in mobility and independence (A3), and the training
changes sensory cortex (A5). Virtual navigation over headphones is learnable and
generalises to untrained virtual spaces (A4).

Not known: whether training on a computer *alone* transfers to navigation in the real
world. The study we take as our template trained people in the lab, on a computer and
outdoors together, and names this as an open question (A3). SoundSight must not claim
that it works until that has been tested, and stage S2 exists partly to make the test
possible.

## Stages

### S1. Click coach (built; gates open)

Analyse a recording of the user's clicks and report, in plain language, whether they are
short, consistent and clean enough. Reference ranges follow B1 and remain provisional
until calibrated with instructors.

### S2. Acoustic engine and the first exercise pack (in progress)

- The engine of [decision 2](decisions/0002-acoustic-engine.md): mirror reflections
  plus edge diffraction, compact scatterers, impulse responses in the time domain,
  admitted problem by problem through the conformance matrix. Increment 1 (one thin
  plate, first-order diffraction) exists; on the size-discrimination discs of A3
  (EXP-0003) it is valid for 10 of 15 trials, and the rest use wave-solver echoes. EXP-0004
  chose diffraction of all orders (C2) as increment 2: valid for all 15 trials, but too
  slow for full-band impulse responses as it stands. Next: rendering exercise audio with
  it within budget, then several objects with occlusion.
- Exercises rendered in advance and played over headphones, triggered by the user, with
  the user's own recorded click. Template: the tasks of A3 (size discrimination,
  orientation, maze navigation with mirror-image transfer mazes, a no-click control).
- Design points taken from the literature: keep room reverberation in the exercises
  (G1 found novices did better in a reverberant room); track the number and loudness of
  clicks, not only success (B2); add noise ladders (C1); check and report differences
  between the user's two ears, which predicted learning in virtual tasks (A3).
- Built with blind co-designers from the first prototype.

### S3. Interactive listening with head tracking

The same pre-computed responses, selected by head orientation from earbuds or a phone,
with triggered clicks, so latency shifts everything together and does no harm. A generic
HRTF first (F1: left-right cues survive, front-back confusions increase, which head
movement resolves), exchanged in the SOFA format (E4). The first target device follows
what our co-designers use. The stack experiment EXP-0001 is revised and run here.

### S4. Personal scenes

Scan a familiar room with a phone, simplify it, assign surface materials, and generate
exercises in it. Scans of homes are personal data and stay on the user's device unless
they choose otherwise.

### S5. Live clicks on dedicated hardware

The user clicks and hears virtual echoes of that click (precedent: C2). An echo from
distance d must arrive 2d/c after the click, 5.8 ms for 1 m, so total latency decides the
nearest object that can be rendered. This needs dedicated low-latency audio hardware and
a quiet, non-reverberant space. It is a tool for laboratories and mobility centres, and
the instrument for comparing virtual echoes with real ones.

## Not scheduled

Proposed in the 2026-11-15 draft and recorded so they are not lost: an online layer with
shared scenarios and competitions, a mobile companion with parity to the desktop tools,
and a validation-report service for acoustic consultants. None is planned until S2 has
shown that the training works.

## Validation that runs through every stage

1. Physics: every engine answers canonical problems against exact solutions and a wave
   solver ([validation](acoustics/validation.md)).
2. Measurement: simulated echoes against recorded ones, starting with the simple scenes
   of the BRAS dataset (E3) and then our own binaural recordings. Not started.
3. People: do trainees improve, and does it transfer? Needs an ethics-approved study
   with our academic partners. Not started.
