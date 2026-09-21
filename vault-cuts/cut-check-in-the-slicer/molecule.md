---
source:
- docs/rfc/jev-cuts-brief.md:62
- docs/rfc/jev-cuts-brief.md:65
status: sliced
sliced_atoms: 4fa803313182a12b
---

## Goal

run_answer takes an optional checker and runs it on a validated molecule before the review is paid for. Findings come back as a refusal the repair round already handles, and a changed molecule is validated again.

## Why

The brief wants the check to sit between validation and the independent review, and to feed the existing repair path. That wiring is the one part no existing molecule covers.

## Needs

- [[cut-check/molecule]]
