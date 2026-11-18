# SoundSight

SoundSight is an open toolkit for training human echolocation: a "virtual gym" where
people, blind people first of all, can practise hearing the echoes of their own tongue
clicks. The aim is agency and independence: a skill that stays with the person, not a
device they must depend on.

**Status: pre-alpha, stage 1.** What works today is the *click coach*: it checks a
recording of tongue clicks and reports, in plain language, how long and how high they are,
how consistent, and whether the recording is good enough to use. The acoustic engine that
will produce the echoes is being built against a published validation suite: see
[how the acoustics is validated](docs/acoustics/validation.md) and
[why it uses rays with edge diffraction](docs/decisions/0002-acoustic-engine.md).

## Accessibility first

Every output is designed to be used with a screen reader. Command-line reports are
linear text, one fact per line, units spelled out, no tables or symbols. If anything in
SoundSight is awkward to use without sight, that is a bug: please report it.

## Try it

SoundSight needs Python 3.13 or newer. With [uv](https://docs.astral.sh/uv/) installed,
from a clone of this repository:

```
uv run soundsight click synth example.wav
uv run soundsight click analyze example.wav
uv run soundsight click analyze my-clicks.wav --verbose
```

`synth` writes ten synthetic clicks; `analyze` checks any WAV file with five or more
clicks, about one per second. Add `--json` for a machine-readable report and `--strict`
to get a non-zero exit status when a check fails.

### Recording your clicks

Use the same setup every time: the microphone at a fixed distance in front of your
mouth, a quiet room with soft furnishings (or outdoors away from walls), and an input
level where the loudest click stays well below the maximum. Click at least five times,
about once per second. The analysis tells you if the recording overloaded or the room
was too noisy.

The reference ranges used by the checks are **provisional**. They follow published
descriptions of expert echolocators' clicks loosely and will be calibrated with
echolocation instructors and researchers before being offered as targets.

## Plan and evidence

- [Roadmap](docs/roadmap.md): the stages, and what is not yet known.
- [Quality gates](docs/quality/quality-gates.md): how each stage's success is measured,
  decided before it is built.
- [Research base](docs/research/literature.md): the literature behind each decision,
  checked against publisher records.
- [Experiments](docs/experiments/README.md): decisions are made by measurement, with
  thresholds fixed in advance.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: `uv run python tools/check_all.py`
runs the same checks as continuous integration.

## History

SoundSight began in 2016 as a project of the SCImPULSE Foundation. The original
demonstrator ([SoundSight/SoundSight](https://github.com/SoundSight/SoundSight)) was
built on a closed, non-commercial acoustics library and could not be developed further.
This repository is a fresh start; [docs/decisions](docs/decisions) explains why, and
[docs/legacy-2016.md](docs/legacy-2016.md) records what the demonstrator did.

## Acknowledgements

SoundSight began as a project of the SCImPULSE Foundation. The quality-gate structure,
the pre-registration rule for experiments, the dependency-licence allowlist, the
evidence-citation check and the first draft of the research base were contributed by
Kimi (kimi.ai) in a working session with the project lead on 2026-11-15; they were then
reviewed, checked against PubMed and revised. Kimi also contributed the first exercise
trial renderer (2026-11-18), integrated after review as candidate R1 of EXP-0005. Much of the code and documentation was
written with Claude (Anthropic).

## Licence

Apache License 2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE). The repository follows
the [REUSE](https://reuse.software) specification, so the licence of every file is
machine-readable.
