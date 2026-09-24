---
source:
- vault/specs/brief-fidelity-and-return-path.md:46
- vault/specs/brief-fidelity-and-return-path.md:48
- vault/specs/grilling-interview-record.md:55
- docs/rfc/grilling-stage-interfaces.md:29
- docs/rfc/grilling-stage-interfaces.md:62
files:
- grill/late.py
- grill/tests/test_late.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
sliced_atoms: ffc859316c1532cf
---

## Goal

grill/late.py:record_question(session, wording, affected_work) adds a pending question to session/decisions.yaml and one late_question row to session/session.jsonl, and changes nothing else. grill/late.py:open_questions(session) lists the pending late questions with their wording and affected work.

## Why

A later stage that finds a missing decision must be able to record it in the same decision record without restarting the interview. The gate can show that nothing settled is touched. It cannot show that no resolved question is asked again, because that is behaviour of the asking code. The brief's not-ready state (brief.ready) is a separate idea and is left out.

## Done when

The test starts from a session with one resolved question, one pending question and an existing session.jsonl line, plus other files that it hashes. After record_question, the decisions.yaml questions map has exactly one new key, with state pending and decision null, and every earlier entry is equal to what it was. session.jsonl has exactly one new line after the old bytes, which are unchanged. That line has kind late_question and carries the given wording and affected_work. No other file in the session directory has changed. open_questions returns a value whose repr contains the wording and affected_work of the recorded question while it is pending, and does not contain them once the test edits that entry to resolved directly in decisions.yaml. With no late question recorded, open_questions does not mention any wording. A record_question that only appends the log row fails the decisions.yaml check. One that only writes the record fails the row check. An open_questions that returns nothing fails the pending case.

## Gate

```sh
set -e -o pipefail
(cd grill/tests && timeout 600 python3 -m unittest test_late)
```

## Creates

- [[grill/late.py:record_question]]
- [[grill/late.py:open_questions]]

## Note

grill/ does not exist yet, so both files are new. The test puts the repository root on sys.path itself so the gate can run from grill/tests. grill/late.py reads and writes decisions.yaml (whole file, through a sibling temporary file) and appends to session.jsonl by itself, with yaml and json only. It does not import grill/record.py or grill/session_log.py, which are not built yet. How a new question gets its id, and how the log row names the record entry, are private to late.py. The test builds its fixtures by writing decisions.yaml in the shape declared in docs/rfc/grilling-stage-interfaces.md, and never calls grill/resolve.py.
