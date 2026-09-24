---
source:
- vault/specs/planning-call-log.md:9
- docs/rfc/grilling-stage-decisions.md:1
status: sliced
sliced_atoms: d0781c50347dceec
---

## Goal

With no campaign directory set, the planning model-call layer prints one message saying nothing is being logged, once per process, and still writes no log files.

## Why

Acceptance item 5 of the planning call log requires that a writer run without a campaign directory works as before and says once that nothing is being logged.
