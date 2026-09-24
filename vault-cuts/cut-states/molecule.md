---
source:
- docs/rfc/jev-cuts-brief.md:44
- docs/rfc/jev-cuts-brief.md:61
status: sliced
sliced_atoms: 31e2288dcd37a28d
---

## Goal

Add slicer/cut_states.py, which keeps the campaign's switch for the decisions-model cut check (off, observe or act) in a file, with the history of who switched it and when.

## Why

Nothing may be asked of the decisions model until a person has switched it on, and an absent file must mean off, so the slicer behaves as it does today until someone chooses otherwise.
