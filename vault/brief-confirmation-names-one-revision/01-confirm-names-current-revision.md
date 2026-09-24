---
files:
- grill/brief.py
- grill/tests/test_brief_confirm.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
---

## Goal

confirm(session, revision, by) reads session/brief.md front matter {revision, request, confirmed}. With revision equal to the front matter revision it sets confirmed to {by, at} and leaves the body unchanged. With revision None, or a different revision, it raises ValueError and leaves session/brief.md byte for byte unchanged. It writes no other file in the session.

## Done when

The test writes a brief.md with revision 2 and no confirmation. It shows that confirm(session, 2, "x") sets confirmed with by "x" and leaves the body unchanged. It shows that confirm(session, None, "x") and confirm(session, 1, "x") each raise ValueError and leave the file bytes and the session's file list unchanged.

## Gate

```sh
set -e -o pipefail
python -m unittest discover -s grill/tests -p test_brief_confirm.py

```

## Uses

- [[docs/rfc/grilling-stage-interfaces.md:brief.md]]

## Creates

- [[grill/brief.py:confirm]]

## Note

Both files are new or shared with the brief-lists-only-current-decisions atom, which is why that molecule is in needs. Add confirm to grill/brief.py without changing compose. The test writes its own brief.md using the front matter shape declared in docs/rfc/grilling-stage-interfaces.md. Readiness is not part of this atom.
