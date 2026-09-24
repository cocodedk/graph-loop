---
source:
- docs/rfc/jev-cuts-brief.md:72
- docs/rfc/jev-cuts-brief.md:44
status: sliced
sliced_atoms: 11aee50fd0c20845
---

## Goal

Add the `cuts` subcommand to graph-goal.py. `cuts --state off|observe|act --by NAME` switches the campaign's decisions-model state, and bare `cuts` prints the state with its history.

## Why

Nothing else lets a person turn the check on, and the brief says only a person switches it to act.

## Needs

- [[cut-states/01-cut-states-module]]
