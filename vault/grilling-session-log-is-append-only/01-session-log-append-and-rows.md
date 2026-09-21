---
files:
- grill/session_log.py
- grill/tests/test_session_log.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
---

## Goal

grill/session_log.py:append(session, row) appends row as one JSON line to session/session.jsonl, creating the file if it is absent. grill/session_log.py:rows(session) returns the rows in the order they were appended, and an empty list when the file does not exist. A request row with outcome timeout comes back like any other row. A second append leaves the bytes already in the file unchanged.

## Done when

The test imports grill.session_log by putting the repository root on sys.path, and uses a directory made with tempfile as the session. It asserts four things. (1) Two appended rows, an answer row and a request row with outcome timeout, come back from rows() equal and in order. (2) After the second append the file holds exactly two lines, and the first line is byte-identical to what it was after the first append. (3) rows() on a session with no session.jsonl returns []. (4) The run collects at least one test, checked with countTestCases() and not a literal. Today the gate fails because grill/session_log.py does not exist.

## Gate

```sh
set -e -o pipefail
(cd grill/tests && timeout 600 python3 -m unittest test_session_log)

```

## Note

Files are grill/session_log.py and grill/tests/test_session_log.py only. grill/record.py stays with the existing molecule. resume_point(session) is granted by the interfaces note but neither approved source says what it returns, so this card does not build or assert it. No tmp_root import, because that helper lives under slicer/tests.
