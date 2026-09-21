---
source:
- docs/rfc/jev-cuts-brief.md:42
- docs/rfc/jev-cuts-brief.md:47
- docs/rfc/jev-cuts-brief.md:50
status: sliced
sliced_atoms: 182f196425050641
---

## Goal

Add slicer/cut_questions.py, a pure module that turns a proposed molecule into the typed questions a decisions model is asked: one cut question per adjacent pair of atoms, and three quality questions per atom.

## Why

The decisions model judges each cut and each atom before the paid review. Both the check and the verdict reader need these questions built the same way, from the molecule alone.
