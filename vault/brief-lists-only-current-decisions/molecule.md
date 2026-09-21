---
source:
- vault/specs/grilling-brief-confirmation-handoff.md:20
- docs/rfc/grilling-stage-interfaces.md:73
files:
- grill/brief.py
- grill/tests/test_brief_decisions.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
sliced_atoms: 47f28d4bbfb24a78
---

## Goal

grill/brief.py:compose(session) writes session/brief.md with a "### <question id>" heading under "## Decisions" for each resolved decision in session/decisions.yaml, and for nothing else. A pending question and a superseded decision never appear as a decision.

## Why

Specification acceptance 2 requires that a brief hold no pending reply and no superseded decision as a decision. The question id is the decision's stable identifier.

## Done when

grill/tests/test_brief_decisions.py builds a session directory whose decisions.yaml (the shape in docs/rfc/grilling-stage-interfaces.md) holds one resolved question, one pending question, and one question with a superseded entry plus a new resolved decision. It calls grill/brief.py:compose(session) and reads session/brief.md. It asserts three things. The "## Decisions" section has a "### <id>" heading for the resolved question and for the re-resolved question. The pending question id is absent from the brief. The superseded text is absent from the brief. Before grill/brief.py exists, the gate fails because the module cannot be imported. The test must also fail if compose lists every question id, so it asserts the pending id and the superseded text are absent.

## Gate

```sh
set -e -o pipefail
(cd grill/tests && timeout 600 python3 -m unittest test_brief_decisions)

```

## Note

The test file and grill/brief.py are both new. compose reads decisions.yaml itself with PyYAML and does not import grill/record.py, which another molecule creates. The body sections other than "## Decisions" may be empty headings.
