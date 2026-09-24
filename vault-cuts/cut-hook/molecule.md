---
source:
- docs/rfc/jev-cuts-brief.md:8
- docs/rfc/jev-cuts-brief.md:61
status: sliced
sliced_atoms: 18e1eb4a87b8b3d2
---

## Goal

Give the slicer one small builder that turns the campaign's decisions-model check into the single-argument checker that run_answer accepts.

## Why

run_answer takes a checker(molecule) callable, and the check takes (molecule, campaign, space, ask, wall). Something has to bind the campaign, space, ask and wall so the slicer can pass one callable. That binding is testable without the network.

## Needs

- [[cut-check/molecule]]
- [[cut-check-in-the-slicer/molecule]]
