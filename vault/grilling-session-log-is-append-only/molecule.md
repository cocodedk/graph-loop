---
source:
- docs/rfc/grilling-stage-interfaces.md:21
- docs/rfc/grilling-stage-interfaces.md:57
- vault/specs/grilling-interview-record.md:62
- vault/specs/grilling-interview-record.md:66
status: sliced
sliced_atoms: 3929134aa7145748
---

## Goal

grill/session_log.py keeps the session record in session/session.jsonl. It is written only by appending one JSON object per line, and every request row is kept, including failed ones.

## Why

The record must show what was spent, not only what succeeded, and it must survive an interruption. That needs an append-only log that never rewrites earlier rows.
