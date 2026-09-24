---
source:
- docs/rfc/jev-cuts-brief.md:43
- docs/rfc/jev-cuts-brief.md:53
status: sliced
sliced_atoms: e3f6c241f6138b05
---

## Goal

Add slicer/cut_verdicts.py, a pure module that reads a decisions model's answers into verdicts and says which atoms to merge and which findings to raise.

## Why

The brief grants read, merges, findings and apply_merges as the pure half of the cut check. Only usable verdicts at or above the 0.6 gate may change a molecule, and a verdict alone never accepts or refuses it.
