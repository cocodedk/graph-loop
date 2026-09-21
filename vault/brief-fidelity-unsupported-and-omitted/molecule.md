---
source:
- docs/rfc/grilling-stage-interfaces.md:28
- vault/specs/brief-fidelity-and-return-path.md:31
- vault/specs/brief-fidelity-and-return-path.md:32
- vault/specs/brief-fidelity-and-return-path.md:36
status: sliced
sliced_atoms: e644e23b7b16c3dd
---

## Goal

The fidelity check compares the "### <question id>" headings of a brief with the current resolved decisions of the record. It reports an unsupported finding for a decision the record does not support, and an omitted finding for a current decision the brief leaves out.

## Why

The independent review must refuse a brief that states a revised answer, a superseded delegation or a partial reply. It must equally refuse a brief that drops a current decision. This is the part of the review that needs no model call and that a gate can observe.
