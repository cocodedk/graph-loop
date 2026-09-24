---
source:
- docs/rfc/grilling-stage-interfaces.md:83
- vault/specs/grilling-evaluation-and-state-switching.md:20
- vault/specs/grilling-evaluation-and-state-switching.md:21
- vault/specs/grilling-evaluation-and-state-switching.md:22
files:
- grill/evaluate.py
- grill/tests/test_evaluate_report.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
sliced_atoms: 77750fd38d908fe4
---

## Goal

grill/evaluate.py:report(sessions, annotations) returns the report.yaml shape from docs/rfc/grilling-stage-interfaces.md, computing the mechanical figures from session.jsonl alone and never reporting an unknown judgment measure as zero.

## Why

The state switch to act reads categories[what].reviewed from a report. The spec requires unannotated judgment measures to say "not annotated" and calls avoided to say "no baseline", never a number that looks like a measurement.

## Done when

In grill/evaluate.py, report(sessions, annotations) takes sessions as a list of session directory paths, each holding a session.jsonl in the shape from docs/rfc/grilling-stage-interfaces.md, and annotations as a list of annotations.yaml entries (empty when there are none). It returns a dict with keys sessions, categories, mechanical, judgment and calls_avoided. sessions is the number of session directories given. categories has a key for each of answers, answers_part, may_contradict, new_requirement, unclear and choose, each with reviewed 0, disagreed [] and unannotated equal to the number of examples for that category in the given sessions when annotations is empty. This card fills reviewed and disagreed only with those empty-annotation values. mechanical.wait_seconds is computed per turn as the sum of the seconds of that turn's request rows, whatever their outcome, so a timeout counts. median is the median of those per-turn sums and slowest is the largest. mechanical.cost is the sum of the cost values of request rows that have one, and is the string "not recorded" when no request row has a cost. mechanical.repeated_questions is the number of asked rows for a question id that come after a resolved row for the same id. With annotations empty, each of judgment's unnecessary_question, wrongly_answered, contradiction_missed, brief_lost_or_altered and reviewer_gaps is the string "not annotated", and calls_avoided is the string "no baseline". The test uses two fixture sessions built in a temporary directory with different seconds values, one request row without cost, and one asked row after a resolved row for the same question. It asserts the exact numbers, so a stub that returns constants fails. It asserts judgment values equal the string, not merely falsy. It makes no network call.

## Gate

```sh
set -e -o pipefail
(cd grill/tests && timeout 600 python3 -m unittest test_evaluate_report)

```

## Note

New files only: grill/evaluate.py and grill/tests/test_evaluate_report.py. Do not touch any other grill/ file. Import the session.jsonl rows by reading the JSON lines directly; do not depend on grill/session_log.py, which another card owns. Mirror the import convention of the existing test files under slicer/tests so that the gate command run from grill/tests finds the grill package. Write fixtures with tempfile under the system temp directory in the test, never inside the repository. Filling categories from annotations, computing judgment measures from annotations, and calls_avoided against a text-model-only baseline are later work; report and replay in evaluate.py grow there. Keep evaluate.py under 200 lines.
