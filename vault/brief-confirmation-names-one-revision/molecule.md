---
source:
- vault/specs/grilling-brief-confirmation-handoff.md:24
- docs/rfc/grilling-stage-interfaces.md:73
status: sliced
sliced_atoms: f79904416b0f5b69
---

## Goal

grill/brief.py:confirm(session, revision, by) records a confirmation in the front matter of session/brief.md only when revision names the brief's current revision. It refuses a missing revision and a revision that is not the current one, and a refusal changes nothing on disk.

## Why

The spec requires that a confirmation applies to one named revision. Nothing in the repository yet writes or refuses a confirmation.

## Needs

- [[brief-lists-only-current-decisions/molecule]]
