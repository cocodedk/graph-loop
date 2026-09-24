---
source:
- docs/rfc/grilling-stage-interfaces.md:90
- docs/rfc/grilling-stage-interfaces.md:93
- vault/specs/grilling-brief-confirmation-handoff.md:24
- vault/specs/grilling-brief-confirmation-handoff.md:25
files:
- grill/handoff.py
- grill/tests/test_handoff.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
sliced_atoms: 8e753b8d1580bbdb
---

## Goal

grill/handoff.py:confirmed_block(brief_file, revision) reads a brief.md and returns its text and revision as one separate prompt block. It raises ValueError when the brief's front matter shows no confirmation of that revision.

## Why

The spec requires that a confirmed brief and its revision travel as their own input, and that an unconfirmed brief is never handed on. Both slicer entry points need the same guard, so it exists once, before either is wired.

## Done when

grill/tests/test_handoff.py runs under the gate and passes. Its tests insert the repository root into sys.path and import grill.handoff. A brief.md written to a temp directory has front matter {revision, request, confirmed} in the shape declared in docs/rfc/grilling-stage-interfaces.md. For a brief with confirmed set to {by, at} and revision 2, confirmed_block(path, 2) returns a string that contains the body text and the revision number, and the string differs from the raw file text. It raises ValueError for a brief whose confirmed is null. It raises ValueError when revision 3 is asked of a brief confirmed at revision 2. It raises ValueError when revision is None. Before the work the gate fails with ImportError, because grill/handoff.py does not exist. The gate proves only this guard, not the wiring into slicer/branches.py or slicer/speccer.py.

## Gate

```sh
set -e -o pipefail
(cd grill/tests && timeout 600 python3 -m unittest test_handoff)

```

## Note

Only the two listed files are written. grill/handoff.py is a new file. Front matter is the YAML between the leading --- lines, read with PyYAML, which is the only runtime dependency. The function reads the file and writes nothing. slicer/branches.py and slicer/speccer.py are untouched.
