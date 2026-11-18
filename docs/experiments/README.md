# Experiments

Decisions that depend on measurement are made by experiment, recorded here as
`EXP-NNNN-short-name.md`. Decision records cite them on their "Experiments:" line, and
CI checks that every cited experiment exists (`tools/check_docs.py`).

## The pre-registration rule

Proposed by Kimi (kimi.ai) on 2026-11-15 and adopted for all experiments from EXP-0003.

1. Before any measurement, the experiment file states the question, the workload, the
   metrics and the thresholds that will decide the outcome, and is committed.
2. No option may be judged on a criterion added after results are seen. If a criterion
   turns out to be wrong, the change and the reason are recorded in the file, dated.
3. Results are added to the same file; the protocol section is not rewritten.
4. An experiment run before its protocol was committed is labelled **retrospective**.
   It may support a decision, but its thresholds do not have the standing of
   pre-registered ones.

Thresholds that CI enforces live in `docs/quality/budgets.toml`, each marked as
pre-registered or retrospective.

| ID | Question | Status |
| --- | --- | --- |
| EXP-0001 | Which language and libraries for the real-time kernel? | Protocol drafted; deferred, to be revised before it runs |
| EXP-0002 | Waves or rays for the acoustic engine? | Complete; retrospective |
| EXP-0003 | Does the engine reproduce the echoes of the size-discrimination discs? | Run 2026-11-16, corrected 2026-11-17: valid for 10 of 15 trials; re-run by CI |
| EXP-0005 | How to render exercise trials with the accuracy of increment 2, within budget? | Pre-registered 2026-11-18; R1 contributed by Kimi (kimi.ai), revised on review |
| EXP-0004 | Which higher-order edge diffraction closes the gap? | Concluded 2026-11-17: no candidate passes every gate; C2 (all orders) becomes engine increment 2 by rule 3; full-band rendering cost is the next problem |
