---
source:
- docs/rfc/grilling-stage.md:1
- vault/specs/grilling-interview-record.md:48
status: sliced
sliced_atoms: 9c6bd03028b17f13
---

## Goal

grill/resolve.py writes a later resolved decision on a question into session/decisions.yaml. The earlier decision stays word for word, marked superseded and naming the decision that replaced it.

## Why

The spec says a superseded decision stays in the record and is never current. Writing that needs a writer, and the existing molecules only read.

## Needs

- [[grilling-record-reads-current-and-pending/molecule]]
