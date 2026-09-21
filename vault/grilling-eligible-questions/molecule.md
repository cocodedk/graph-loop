---
source:
- vault/specs/grilling-opening-analysis-and-selection.md:47
- docs/rfc/grilling-stage-interfaces.md:22
status: sliced
sliced_atoms: 3137a77e5359949e
---

## Goal

grill/questions.py:eligible(analysis, record) returns the ids of the questions that may be asked now. A question is eligible only while its prerequisites are all resolved, it is pending, and it is in scope. An analysis that is not completed yields no eligible question.

## Why

Selection can only ever pick an eligible question. Nothing else in the plan yet says which questions those are.

## Needs

- [[grilling-analysis-stored-only-when-complete/molecule]]
