---
source:
- docs/rfc/grilling-stage-decisions.md:106
- vault/specs/grilling-interview-record.md:40
status: sliced
sliced_atoms: 82b00b3d5ecfaefc
---

## Goal

grill/record.py reads a session's decisions.yaml. current(record) holds only the resolved decisions. A pending question, and a decision that has been superseded, are never in it.

## Why

D5 says a pending reply and a superseded decision are never current, and the specification (items 6 and 9) repeats it. Every later grilling module (selection, routing, brief fidelity) reads this record, so it comes first and stands alone.
