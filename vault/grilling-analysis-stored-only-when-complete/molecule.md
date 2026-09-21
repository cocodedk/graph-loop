---
source:
- vault/specs/grilling-opening-analysis-and-selection.md:29
- docs/rfc/grilling-stage-interfaces.md:22
files:
- grill/questions.py
- grill/tests/test_questions_save.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
sliced_atoms: 6f1caa537b6e620a
---

## Goal

grill/questions.py:save(session, analysis) writes session/analysis.yaml only for a completed analysis, and writes nothing for an incomplete one.

## Why

Later stages ask questions from analysis.yaml. A set that is part-way, or that has an unreasoned or repeated asking order, must never reach it. Otherwise a question could be asked from a failed analysis.

## Done when

The gate passes. Case (a) shows a complete set is stored unchanged. Each of cases (b) to (f) leaves session/analysis.yaml absent. Before the work, the gate fails because grill/questions.py does not exist. The gate proves storage only for these cases. It does not prove eligibility, selection, follow-ups, or how a failed attempt is recorded.

## Gate

```sh
set -e -o pipefail
(cd grill/tests && timeout 600 python3 -m unittest test_questions_save)

```

## Note

Both files are new. The test inserts the parent directory (grill/) into sys.path itself, because the gate runs from grill/tests, and imports `questions`. It uses a fresh temporary session directory per case. It reads results only through the file session/analysis.yaml, using yaml.safe_load and os.path.exists. It does not depend on what save returns or whether it raises, so each save call is wrapped in try/except Exception. Analyses use the shape in docs/rfc/grilling-stage-interfaces.md, with `completed: true` and `order: {position, reason}` as integer positions. Do not require any base for positions; the valid case uses 1..n and only distinctness is enforced. The cases are, in each one, "nothing stored" means analysis.yaml is absent. (a) A valid two-question set is stored, and the file loads back equal to the input. (b) The same set with `completed: false` is not stored. (c) A question missing `consequence` is not stored. (d) An `order.reason` that is empty is not stored. (e) Two questions with the same `order.position` are not stored. (f) Two questions with the same `id` are not stored. Each of (b) to (f) is derived from the valid set in (a) by changing exactly one thing. Case (a) is what stops an implementation that refuses everything from passing.
