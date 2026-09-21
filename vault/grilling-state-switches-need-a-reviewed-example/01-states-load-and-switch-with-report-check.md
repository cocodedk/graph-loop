---
files:
- grill/states.py
- grill/tests/test_states.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
---

## Goal

grill/states.py:load(session) returns the states.yaml shape from docs/rfc/grilling-stage-interfaces.md. With no states.yaml, interpret and choose are both off, act_kinds is empty and history is empty. grill/states.py:switch(session, what, to, by, report=None) records a switch. A switch to observe or off needs no report. A switch to act needs report, the path of a report.yaml, and is refused when that report's categories entry for what has reviewed below 1, or has no entry. A refused switch changes nothing on disk.

## Done when

The test writes its session directory and its report.yaml fixtures under a temporary directory. The fixtures use the report.yaml shape from docs/rfc/grilling-stage-interfaces.md. The test shows that: (1) load on a session with no states.yaml gives both states off, empty act_kinds and empty history; (2) switch(session, "choose", "observe", by) with no report succeeds and appends a history row holding what, to, by, at and report; (3) switch to act for "choose" with no report raises, and states.yaml is absent or byte-identical afterward, with no new history row; (4) the same switch with a report whose categories.choose.reviewed is 0, or has no choose entry, raises and changes nothing; (5) the same switch with reviewed 1 succeeds, sets choose.state to act, and the history row carries the report path; (6) switch(session, "answers", "act", by, report) with categories.answers.reviewed 1 sets interpret.state to act and act_kinds to ["answers"]. The test catches any Exception for the refusals, because the source does not name an exception type. The test does not claim a threshold or that a category is reliable.

## Gate

```sh
set -e -o pipefail
(cd grill/tests && timeout 600 python3 -m unittest test_states)

```

## Creates

- [[grill/states.py:load]]
- [[grill/states.py:switch]]

## Note

File boundaries: only grill/states.py and grill/tests/test_states.py. grill/ has no __init__.py requirement beyond what the sibling molecules create; the test imports the module as the other grill tests do, with the path set up inside the test file, and must not depend on any other grill module. Pinned encoding of `what`, because the switch has no separate kind parameter: `what` is "choose", "interpret" or one of the five answer_kind values (answers, answers_part, may_contradict, new_requirement, unclear). Switching an answer kind to a state sets interpret.state to that state, and to act appends the kind to interpret.act_kinds without duplicates. `report` is the path of a report.yaml. For an answer kind or for "choose" the check reads categories[what].reviewed. "interpret" itself is not a category, so switching it to act is refused. A refusal is any raised exception, and the refusal message must not claim the category is reliable. Write states.yaml whole through a sibling temporary file and rename it. The gate cannot observe this; it is a required method. No confidence threshold in this atom (acceptance 9 is a separate idea). Add no GRAPH_* environment name. The only dependency is PyYAML. Keep files under 200 lines and make `ruff check .` pass.
