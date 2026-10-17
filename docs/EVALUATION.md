# Evaluation and human review

There are two independent measurements:

1. Automated **substring/section regression assertions** detect known failures. They do not measure semantic accuracy.
2. **Human claim review** records whether each statement is supported, unsupported, contradicted, incorrectly attributed, or uncertain, plus omitted facts. No semantic score is reported until a reviewer supplies annotations.

Export a packet from a recorded model run:

```sh
.venv/bin/python -m evaluations.review evaluations/qwen3-local.json --output evaluations/review-packet.json
```

For every case, compare each claim against the transcript and cited turns, add a label and rationale, explicitly record omissions (or an empty list), and fill reviewer and reviewed_at. Do not use a model's own judgment as ground truth. Prefer a second independent reviewer to discuss disagreements.

Validate annotations:

```sh
.venv/bin/python -m evaluations.review evaluations/qwen3-local.json --annotations evaluations/review-packet.json --output evaluations/review-summary.json
```

Packets bind to a run ID and exact note hash. Modified notes, missing claims and duplicate cases are rejected. Partial coverage is reported; unreviewed output is unknown, never a passing score. These are synthetic portfolio examples, not clinical validation.

Run a separate dataset with `python -m evaluations.run --provider ollama --cases path/to/cases.json --output path/to/report.json`. Author and freeze evaluation examples before changing prompts; once used for tuning, treat them as development examples and create a new holdout. Reports include a dataset hash.

## Interview walkthrough

Show a source transcript, the generated note, and a correction that requires judgment. Explain the distinction between schema validation, citation validity, and factual support. Show a failing regression and reviewer annotation before discussing improvements. Never report 25/30 synthetic cases as clinical accuracy.

## Correction experiment: a tradeoff, not a new accuracy claim

The recorded `grounded-v2` run passed 25/30 development cases. Its five failures retained superseded durations after an explicit patient correction. The experimental `corrections-v3` prompt passed 26/30 on the same dataset and fixed those correction cases, but introduced four omissions of the patient's explicit denial of a family member's diagnosis. The recorded output is in `evaluations/qwen3-corrections-v3.json`.

The net gain of one case hides a regression in attribution detail. Therefore v3 is selectable for comparison, not promoted to the default. Both runs use substring/section assertions, not clinician-reviewed semantic accuracy. The development set was used to design v3; neither run is an independent holdout. Human annotation remains deliberately blank until a reviewer completes the packet.
