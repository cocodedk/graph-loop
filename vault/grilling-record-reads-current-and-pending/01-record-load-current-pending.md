---
files:
- grill/record.py
- grill/tests/test_record_read.py
gate_files_are_the_work: true
may_add_files: true
status: todo
gate_reviewed_first: true
---

## Goal

grill/record.py:load(session) reads session/decisions.yaml. current(record) returns the map of resolved decisions, keyed by question id. pending(record) returns the pending question ids. A question that has a superseded history but a new resolved decision is current with the new one only. A question whose only entries are superseded, with state pending, is pending and not current.

## Done when

The gate exits 0 with at least one test run. Today it fails because grill/record.py does not exist, so the import fails. It proves that load, current and pending follow the declared decisions.yaml shape: resolved decisions of the three kinds are current, pending questions are not, and a superseded decision is never current. It does not prove resolve, supersede, the session log, or any other grilling module.

## Gate

```sh
set -e -o pipefail
out=$(mktemp)
(cd grill/tests && timeout 600 python3 -m unittest -v test_record_read) > "$out" 2>&1 || { tail -30 "$out"; exit 1; }
grep -Eq '^Ran [1-9][0-9]* test' "$out"
grep -q '^OK' "$out"

```

## Creates

- [[grill/record.py:def load]]
- [[grill/record.py:def current]]
- [[grill/record.py:def pending]]

## Note

Two new files. The test puts the parent grill/ directory on sys.path itself, because the gate runs from grill/tests, and adds no __init__.py. The test writes two different decisions.yaml files into temporary session directories, in exactly the shape the interfaces note declares.
Fixture A holds one resolved answer, one resolved delegation, one resolved exclusion, one pending question with decision null, and one question resolved by a new decision that also carries a superseded list.
Fixture B holds a different single question.
The test asserts: (1) set(current(load(A))) is exactly the resolved ids, so the pending id is absent; (2) the superseded text never appears among the values of current, and the current text is the new decision's text; (3) pending(load(A)) contains the pending id and no resolved id; (4) load(B) gives a different result from load(A), which proves that load reads the given session directory.
The test uses only membership and set(...) on the returned values, so it does not fix the container type of pending or the record type. It does not call resolve or supersede.
