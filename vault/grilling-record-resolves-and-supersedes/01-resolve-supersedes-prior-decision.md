---
files:
- grill/resolve.py
- grill/tests/test_resolve.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
---

## Goal

grill/resolve.py:resolve(session, qid, decision) appends a resolved decision to session/decisions.yaml. If the question already had a resolved decision, that entry keeps its text unchanged, gets state superseded, and gets a superseded_by field naming the new decision.

## Done when

The test writes a first decision, then a second on the same question. It asserts that the first is byte-identical apart from state and superseded_by, and that superseded_by names the second. It also asserts that the file holds exactly one resolved decision for that question. The test fails today because grill/resolve.py is absent.

## Gate

```sh
set -e -o pipefail
python -m unittest grill.tests.test_resolve

```
