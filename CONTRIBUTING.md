# Contributing to SoundSight

## Setting up

Install [uv](https://docs.astral.sh/uv/); no administrator rights are needed. Then, in
a clone of the repository:

```
uv sync
uv run python tools/check_all.py
```

`uv sync` creates a private environment in `.venv` with the exact dependency versions
in `uv.lock`. `check_all.py` runs, in order: the repository hygiene check, the licence
check (REUSE), the linter and formatter check (ruff), strict type checking (mypy) and
the test suite with coverage (pytest). Continuous integration runs the same checks.

To run the regression test on the real 2016 click recording, fetch it first:

```
uv run python tools/fetch_legacy_click.py
uv run pytest -m legacy
```

## What continuous integration checks

Every push to `main` and every pull request runs these jobs on GitHub:

| Job | What it guarantees |
| --- | --- |
| Hygiene and licensing | No compiled files, IDE state or files over 512 KiB are tracked; every file has a declared licence (REUSE); every dependency has a known licence on the allowlist in `docs/quality/licenses.toml`; every decision record cites existing literature and experiments. |
| Lint and types | ruff lint and formatting pass; mypy passes in strict mode. |
| Tests | The full suite passes on Linux (Ubuntu 24.04 and 26.04), macOS 26 and Windows Server 2025 with Python 3.13 and 3.14, with at least 95% branch coverage. Warnings are errors. |
| Acoustic validation | Every acoustic model is checked against exact solutions and a validated wave solver, with a declared verdict for each canonical problem (part of the tests above); a separate job repeats the solver's own checks on fine grids. See [docs/acoustics/validation.md](docs/acoustics/validation.md). |
| Lowest dependencies | The suite also passes with the oldest dependency versions `pyproject.toml` claims to support. |
| Next Python | Early warning: the suite runs on the next Python release once numpy, scipy and hypothesis can be imported there (pre-releases usually cannot). Until then the job passes with a notice saying nothing is known; once they can, a test failure turns the job red. It does not block merging. |
| Legacy recording | The analysis still gives the expected results on the real 2016 recording, downloaded from a pinned commit and verified by checksum. |
| Package | The wheel and source distribution build, pass `twine check`, and the installed command works in a clean environment. |
| Dependency audit | No dependency in `uv.lock` has a known vulnerability. |

Supported versions follow SPEC 0, the convention of the scientific Python community
(https://scientific-python.org/specs/spec-0000/): each Python version is supported for
three years after its release, and NumPy and SciPy feature releases for two years. The
floors in `pyproject.toml` are raised accordingly every October, when a new Python
version appears; the lowest-dependencies job then tests the new floors. SoundSight is an
application rather than a library others depend on, so it has no reason to keep older
versions. Development tools are locked and updated by Dependabot.

Runner operating systems are pinned to exact versions, not to GitHub's moving "latest"
labels, so that a change in results always comes from a change in the repository. Nothing
updates them automatically: when GitHub releases a new OS image
(https://github.com/actions/runner-images), update the matrix in `ci.yml` deliberately.

The same workflow also runs weekly, to catch breakage caused by new releases of
dependencies. GitHub Actions are pinned to full commit hashes, and Dependabot proposes
updates to them and to `uv.lock`.

## Rules for contributions

- **New dependencies need a licence review.** CI fails on a dependency whose licence is
  unknown or not on the allowlist. If the licence is acceptable but not machine-readable,
  record what you found in `docs/quality/licenses.toml`.
- **Decisions cite their evidence.** A decision record names the literature entries and
  experiments it rests on; literature is added to the research base only together with
  something that uses it; experiments fix their thresholds before measuring.
- **Acoustic models are admitted by test.** A new engine or approximation is added to
  the conformance matrix with a declared verdict for each canonical problem, and is used
  only within the range where it passes.
- **Tests come with code.** New behaviour needs tests; bug fixes need a test that fails
  without the fix. Prefer tests against synthetic signals with known ground truth.
- **No binaries in git.** Compiled files and large media are rejected by CI.
- **Recordings need consent and a licence.** A recording of a person's clicks, voice or
  home may only be added with that person's written consent and an explicit licence
  (for data, normally CC-BY-4.0), declared in `REUSE.toml`. Room scans of homes are
  personal data: they are never committed to this repository.
- **Accessible output.** Anything a user reads must work with a screen reader: linear
  text, units in words, plain ASCII in command-line output.
- **Licence headers.** New source files start with the same two-line SPDX copyright and
  licence header as the existing ones; the REUSE check fails without it.

By contributing you agree that your contribution is licensed under the Apache License
2.0, as section 5 of that licence describes.
