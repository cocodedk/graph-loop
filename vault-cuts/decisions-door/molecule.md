---
source:
- docs/rfc/jev-cuts-brief.md:41
- docs/rfc/jev-cuts-brief.md:28
- docs/rfc/jev-cuts-brief.md:31
- docs/rfc/jev-cuts-brief.md:70
status: sliced
sliced_atoms: 7e699b3d6129e02e
---

## Goal

Add graph/lib/decisions.py, a general door that asks a decisions model several typed questions about one state in a single call and returns an Answer(ok, answers, seconds, cost, why). It sits beside provider_jev.ask and never raises.

## Why

Every later cut check needs one call that carries many questions, and provider_jev.ask is hardwired to triage's single question. The brief requires that door to be added beside it, without changing it.
