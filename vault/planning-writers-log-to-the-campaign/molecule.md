---
source:
- vault/specs/planning-call-log.md:9
- vault/specs/planning-call-log.md:15
- docs/rfc/grilling-stage-decisions.md:130
status: sliced
sliced_atoms: 5d26a0aa8d4c9c99
---

## Goal

When a campaign directory is given, the spec writer and the branch writer set intelligence.CAMPAIGN, so their writer and reviewer calls land in the campaign's own step, artifact and attempt records, and a reviewer refusal is kept in full.

## Why

In one planning run six of eleven specification submissions were refused and the refusals survived only as one line on standard output. The existing record machinery does the recording once it is switched on, so switching it on is the smallest change.
