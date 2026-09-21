---
source:
- docs/rfc/jev-cuts-brief.md:62
- docs/rfc/jev-cuts-brief.md:71
files:
- slicer/cut_record.py
- slicer/tests/test_cut_record.py
may_add_files: true
gate_files_are_the_work: true
status: done
sliced_atoms: 2714b6f25abacf67
requirement:
  goal: Add slicer/cut_record.py, which wraps a decisions-model ask so that every call is written into
    the campaign's log as an event and as request and answer artifacts, with its timing, cost and reason
    for failing. The answer passes through unchanged and the wrapper never accepts or refuses a molecule.
  done_when: slicer/cut_record.py defines recording(space, ask, label="cut-check"), which returns a callable
    taking (state, questions) and returning exactly what ask returned. Each call writes, through space,
    one event of kind `cut_asked` with the fields ok, seconds, cost, why and questions (the number asked),
    and two artifacts named `cut-request` (the state and questions as JSON) and `cut-answer` (the answers
    as JSON), all under the task id given by label. Fields are read from the returned object with getattr
    defaults, so an answer lacking cost or why still records. When ask returns ok false, the event carries
    its why. When ask raises, an event with why naming the exception is written and the exception is raised
    again. The test builds a real Workspace under $TMPDIR (importing tmp_root) and passes scripted ask
    callables; it makes no network call, and it covers the ok, the not-ok and the raising case.
  sources:
  - docs/rfc/jev-cuts-brief.md:62
  - docs/rfc/jev-cuts-brief.md:71
contract_seen: 62ccfd6810bb6090
accepted_criteria:
  goal: Add slicer/cut_record.py, which wraps a decisions-model ask so that every call is written into
    the campaign's log as an event and as request and answer artifacts, with its timing, cost and reason
    for failing. The answer passes through unchanged and the wrapper never accepts or refuses a molecule.
  gate: 'set -e -o pipefail

    (cd slicer/tests && timeout 600 python3 -m unittest test_cut_record)

    '
  done_when: slicer/cut_record.py defines recording(space, ask, label="cut-check"), which returns a callable
    taking (state, questions) and returning exactly what ask returned. Each call writes, through space,
    one event of kind `cut_asked` with the fields ok, seconds, cost, why and questions (the number asked),
    and two artifacts named `cut-request` (the state and questions as JSON) and `cut-answer` (the answers
    as JSON), all under the task id given by label. Fields are read from the returned object with getattr
    defaults, so an answer lacking cost or why still records. When ask returns ok false, the event carries
    its why. When ask raises, an event with why naming the exception is written and the exception is raised
    again. The test builds a real Workspace under $TMPDIR (importing tmp_root) and passes scripted ask
    callables; it makes no network call, and it covers the ok, the not-ok and the raising case.
  files:
  - slicer/cut_record.py
  - slicer/tests/test_cut_record.py
rebuild_from: /var/tmp/graph-trees/graph-ydxzxhhe/task-cut-record
session: b02bdf83-7f7d-4689-8dab-262f2ad31e38
session_account: personal
rejections:
- 'Diff line 40 (done_when): A raising ask leaves no cut-answer artifact, violating the requirement that
  each call write both artifacts. — After ask raises, the exception handler writes cut_asked and re-raises
  at line 40, bypassing the cut-answer write at lines 41–43. The scripted ValueError case therefore writes
  only cut-request; its test checks the event but never asserts both artifacts exist.'

requeued: true
commit: afe4b6e5eff74f30ae6615604b27bb9e59e3c518
worktree: /var/tmp/graph-trees/graph-ydxzxhhe/task-cut-record
kept_at: '2026-09-20T16:26:59Z'
---

## Goal

Add slicer/cut_record.py, which wraps a decisions-model ask so that every call is written into the campaign's log as an event and as request and answer artifacts, with its timing, cost and reason for failing. The answer passes through unchanged and the wrapper never accepts or refuses a molecule.

## Why

Observe mode is only worth switching on if the requests and verdicts can be read back later, and a decisions model that is down or malformed must leave a stated reason. Wrapping the ask keeps this apart from cut_check.py and cut_verdicts.py, which other cards own.

## Done when

slicer/cut_record.py defines recording(space, ask, label="cut-check"), which returns a callable taking (state, questions) and returning exactly what ask returned. Each call writes, through space, one event of kind `cut_asked` with the fields ok, seconds, cost, why and questions (the number asked), and two artifacts named `cut-request` (the state and questions as JSON) and `cut-answer` (the answers as JSON), all under the task id given by label. Fields are read from the returned object with getattr defaults, so an answer lacking cost or why still records. When ask returns ok false, the event carries its why. When ask raises, an event with why naming the exception is written and the exception is raised again. The test builds a real Workspace under $TMPDIR (importing tmp_root) and passes scripted ask callables; it makes no network call, and it covers the ok, the not-ok and the raising case.

## Gate

```sh
set -e -o pipefail
(cd slicer/tests && timeout 600 python3 -m unittest test_cut_record)

```

## Note

File boundary: only slicer/cut_record.py and its test. Workspace lives in graph/lib/workspace.py; use its `event(kind, **fields)` and `artifact(task_id, name, text)` as they are, and do not edit them. The module must add graph/lib to sys.path the way slicer/tree.py does. It does not read verdicts, merge, or add findings; that stays in cut_verdicts.py. The `report` section and the wiring in slicer.py main are later cards that will read these event and artifact names.
