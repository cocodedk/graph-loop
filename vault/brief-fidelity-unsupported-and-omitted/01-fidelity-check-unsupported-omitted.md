---
files:
- grill/fidelity.py
- grill/tests/test_fidelity_kinds.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
---

## Goal

grill/fidelity.py:check(brief_text, record) returns a list of Finding(kind, decision, consequence). brief_text is a brief.md and record is the decisions.yaml shape, both as declared in docs/rfc/grilling-stage-interfaces.md. The current decisions are the questions whose state is resolved. A "### <qid>" heading under "## Decisions" whose qid is not resolved in record gives one finding of kind unsupported. That covers a pending question and a question whose only entries are superseded. A resolved qid with no such heading gives one finding of kind omitted. Each finding names the qid in decision and has a non-empty consequence. A brief that leaves out a pending or superseded-only question gets no finding for it. A resolved question that also has superseded history is current, and gets no finding when the brief has its heading.

## Done when

test_fidelity_kinds builds its briefs and records from the declared shapes. Each of these cases is asserted and passes. (1) A brief with a heading for a pending question gets an unsupported finding. (2) A brief with a heading for a superseded-only question gets an unsupported finding. (3) A brief that lacks the heading of a resolved question gets an omitted finding. (4) A brief that correctly leaves out both the pending and the superseded-only question gets an empty list. (5) A resolved question with superseded history and a heading in the brief gets no finding. Every finding has decision equal to the qid and a non-empty consequence string. Kinds are compared case-insensitively against "unsupported" and "omitted". The gate fails before the work because grill/fidelity.py is absent, so the import fails. A check that always returns an empty list, or a finding with an empty consequence, fails a positive case.

## Gate

```sh
set -e -o pipefail
(cd grill/tests && timeout 600 python3 -m unittest test_fidelity_kinds)

```

## Note

Two new files, grill/fidelity.py and grill/tests/test_fidelity_kinds.py. The test inserts the repository root into sys.path so that "from grill.fidelity import check" works from grill/tests. check filters state == resolved itself and does not import grill.record, so it needs nothing that has not landed. Left for later molecules: altered, because the body format under a heading is not declared; contradiction and ambiguous, because they need a model and check takes no model callable; readiness, which belongs to brief.ready and not to check. The test must not claim any of these.
