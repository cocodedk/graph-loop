---
source:
- docs/rfc/jev-cuts-brief.md:45
- docs/rfc/jev-cuts-brief.md:61
- docs/rfc/jev-cuts-brief.md:70
status: sliced
sliced_atoms: 7ce2c94da28e1904
---

## Goal

Add slicer/cut_check.py, which runs the decisions-model check on one proposed molecule according to the campaign's switch and never accepts or refuses the molecule itself.

## Why

The slicer needs one pure entry point that turns the switch, the questions, the answers and the verdicts into a molecule and findings, so the wiring into the slicer stays small.

## Needs

- [[cut-questions/molecule]]
- [[cut-states/molecule]]
- [[cut-verdicts/molecule]]
- [[decisions-door/molecule]]
