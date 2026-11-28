# Exercise pack v0: which disc is larger?

The first exercise pack, made to be tried and criticised by blind co-designers before
anyone trains with it. Code: `soundsight.exercise.pack`; generate it with

```
uv run soundsight exercise pack my-pack --click-reference-distance 0.5
```

which takes about a second and writes 30 trials, a player and instructions into
`my-pack/`. To share it, send the folder (about 3 MB). `--click FILE.wav` uses a recording
of the listener's own click (48 kHz) instead of the synthetic one.

## The task

After the size-discrimination task of Norman et al. (2021, literature A3): a 25.4 cm
reference disc against discs of 5.1, 9.0, 13.5, 17.5 and 22.9 cm, at 33, 66 and 99 cm;
each comparison in both orders, 30 trials.

**It is an adaptation, not a replication.** In the study two discs were presented at
once, above and below ear height, and judged by real echoes. Here the engine renders one
disc straight ahead, for one ear, so each trial plays two click-and-echo intervals in
sequence, 0.6 s apart, and asks which disc was larger. The order of trials is shuffled in
every session.

## How the audio is made

Each interval is the click followed by its echo from R3 (EXP-0006): diffraction of all
orders, from per-disc caches stored with the package and checked in CI against a fresh
computation. One gain applies to the whole pack, so the level difference between two
echoes, the cue the listener uses, is exactly the one the engine computes. A test checks
that in every trial the larger disc's echo is louder. Every file is listed in the pack's
`manifest.json` with its SHA-256; regenerating the pack reproduces them.

## The player

`player.html` runs in any browser, offline, with nothing to install. It is built for
screen readers first: one heading per step, keyboard keys (P to play, 1 and 2 to answer),
spoken feedback through a live region, focus moved to each new trial, and a large,
high-contrast layout for low vision, in light and dark mode. Answers, number of plays and
response times are saved at the end as a CSV file for the co-designer to send back.

It was checked here for structure (labelled buttons, live region, embedded manifest) and
its script for syntax; it has **not yet been tried with a screen reader**. That, and
everything a co-designer finds awkward, is the point of v0.

## Open before training

- **Echo level relative to the click.** It depends on what the click recording stands for
  (`--click-reference-distance`, the distance from the mouth at which it was recorded) and
  on the mouth's directivity and the mouth-to-ear path (literature B1). The value used is
  provisional until calibrated with an echolocation instructor or researcher.
- **Screen-reader audit** (quality gate S2): three or more blind co-designers complete the
  pack unaided; whatever stops them is a bug.
- **No claim of training effect.** Whether any computer-only training transfers to real
  navigation is untested (A3); a study needs an ethics-approved protocol.
