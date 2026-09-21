---
source:
- docs/rfc/grilling-stage-decisions.md:38
- docs/rfc/grilling-stage-decisions.md:51
- docs/rfc/grilling-stage-interfaces.md:26
- docs/rfc/grilling-stage-interfaces.md:68
- docs/rfc/grilling-stage-interfaces.md:83
- vault/specs/grilling-evaluation-and-state-switching.md:23
- vault/specs/grilling-evaluation-and-state-switching.md:27
status: sliced
sliced_atoms: 413f4754848bd22d
---

## Goal

grill/states.py starts every state off. It records a person's switches in states.yaml. It refuses a switch to act unless the named report holds at least one reviewed example of that category.

## Why

Acting on the decisions model's result is a person's recorded decision, and the report is the evidence that person looked at (D2, acceptance 7 and 11). Nothing else in the plan builds this switch.
