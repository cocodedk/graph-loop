---
files:
- grill/questions.py
- grill/tests/test_questions_eligible.py
gate_files_are_the_work: true
may_add_files: true
status: todo
gate_reviewed_first: true
---

## Goal

grill/questions.py:eligible(analysis, record) reads analysis as the analysis.yaml shape and record as the decisions.yaml shape from docs/rfc/grilling-stage-interfaces.md. It returns a list of the ids of the questions whose prerequisites are all resolved in record, whose own state in record is pending, and whose in_scope is true. It returns an empty list when analysis has completed false.

## Done when

The test file fails today because eligible does not exist. It then passes, and its cases show each of these leaves a question out of the result. An unresolved prerequisite. A state of resolved. In_scope false. A completed false analysis, which gives an empty list. A question with all prerequisites resolved, pending, and in scope is in the result.

## Gate

```sh
set -e -o pipefail
(cd grill/tests && timeout 600 python3 -m unittest test_questions_eligible)

```

## Needs

- [[grilling-analysis-stored-only-when-complete/molecule]]

## Note

grill/questions.py already exists from grilling-analysis-stored-only-when-complete, so add eligible to it and leave save unchanged. The test file is new. The test builds the analysis and record as plain dicts in the granted shapes, calls eligible directly, and compares sorted ids. It never reads grill/record.py.
