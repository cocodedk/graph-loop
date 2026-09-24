---
source:
- docs/rfc/grilling-stage-decisions.md:106
- vault/specs/grilling-brief-confirmation-handoff.md:23
files:
- grill/brief.py
- grill/tests/test_brief_ready_pending.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
sliced_atoms: c891763572010b45
---

## Goal

grill/brief.py:ready(session) reports a brief not ready while session/decisions.yaml has any question whose state is pending. Ready is not reported for a session with a pending question, whatever else is true of it.

## Why

D5 says a pending question makes the brief not ready. The specification requires that a limit, an empty queue or high confidence never turns a not-ready brief into a ready one, and this shows the pending-question case with only that condition present.

## Done when

The test builds two sessions whose decisions.yaml follows the shape in docs/rfc/grilling-stage-interfaces.md. In one, every question is resolved, and ready(session) is true. In the other, the same record has one question pending, and ready(session) is false. No file in the session changes. The test fails today because grill/brief.py has no ready.

## Gate

```sh
set -e -o pipefail
python -m pytest -q grill/tests/test_brief_ready_pending.py

```

## Needs

- [[brief-confirmation-names-one-revision/01-confirm-names-current-revision]]
- [[brief-lists-only-current-decisions/molecule]]

## Note

grill/brief.py is also written by two earlier tasks, listed in needs, so this task runs after both. The task does not call confirm.
