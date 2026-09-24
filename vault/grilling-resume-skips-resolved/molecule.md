---
source:
- vault/specs/grilling-interview-record.md:76
- docs/rfc/grilling-stage-decisions.md:1
status: sliced
sliced_atoms: 272cd6ac2bd765d0
---

## Goal

After an interruption, grill/resume.py returns the questions still to ask, without any question the record shows as resolved.

## Why

Acceptance item 18 of the interview record specification. Nothing else covers it, and it reads the record the other molecules write.

## Needs

- [[grilling-record-reads-current-and-pending/01-record-load-current-pending]]
- [[grilling-record-resolves-and-supersedes/01-resolve-supersedes-prior-decision]]
