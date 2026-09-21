---
files:
- grill/resume.py
- grill/tests/test_resume.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
---

## Goal

grill/resume.py:remaining(session, queue) returns the ids in queue, in their order, that have no resolved decision in the session record. A pending question and a question whose only entries are superseded stay in the result. A resolved question is never in it.

## Done when

The test covers a queue with one resolved, one pending and one superseded-then-resolved question, and checks that remaining returns only the pending one and keeps the queue order. Before grill/resume.py exists the gate fails on the import.

## Gate

```sh
set -e -o pipefail
python -m pytest -q grill/tests/test_resume.py

```

## Note

grill/resume.py reads the record through grill/record.py. The test builds its session directory by calling grill/resolve.py:resolve, so no file shape is invented here. Both files are new.
