---
status: spec
---

## Needs

- [[vault/01-grilling-interview.md]]

## Goal

Implements decision D1 steps 1 and 2 and the parts of D6 that concern selection, from
docs/rfc/grilling-stage-decisions.md (revision 3, confirmed by the owner). It contradicts none of D1 to D6.
It covers sections 3, 4, 5, 6, 8 and 10 of docs/rfc/grilling-stage.md, limited to:

- the opening analysis by the text model,
- the prepared question set it leaves,
- eligibility, and the first two steps of choosing the next question,
- the update of the analysis when an answer exposes something new.

Before the first question, the text model reads the brief, the repository and the existing decisions.
It finds ambiguities and missing requirements and writes a working set of questions. Step 3 of D1
(the chooser) belongs to the routing specification. This specification leaves that path open.

## Acceptance

1. **Inputs are visible.** The request sent to the text model for the analysis is recorded. The record
   contains the brief text, the repository material given to the model, and every existing decision,
   each by identifier. A set with no such record is not accepted as a completed analysis.
2. **Only a completed analysis counts.** If the analysis fails, times out, returns something that
   cannot be read as a set, or stops part-way, no set is stored and no question is asked. The failure
   is recorded. A later attempt starts from the beginning.
3. **Prepared question fields.** Each prepared question in a completed set has:
   - a stable identifier, unique within the set,
   - its wording,
   - the consequence of leaving it open,
   - its evidence (brief passages, repository facts or earlier decisions),
   - suggested choices, where useful,
   - its prerequisites,
   - prepared follow-ups. Each names the alternative or answer that makes it relevant.
   A question missing a required field makes the analysis incomplete under item 2.
4. **Facts are not asked as open questions.** A fact the repository or an earlier decision already
   supplies does not appear as an open question. Where the user may still need to decide whether
   existing behaviour stays, the question says so and cites the fact as its evidence.
5. **Recorded asking order.** The analysis records one asking order that covers every prepared
   question, follow-ups included, with a stated reason for each position. A set whose order omits a
   question, repeats one, or gives a position no reason is incomplete under item 2.
6. **Eligibility.** A question is eligible only while all three hold: its prerequisites are met, it is
   pending, and its subject is in scope. An ineligible question is never selected.
7. **Selection step 1, the follow-up rule.** When a picked choice or a classified answer matches a
   prepared follow-up that names it, and that follow-up is eligible, that follow-up is asked. No model
   is called for the selection. If more than one eligible follow-up names the same choice or answer,
   the one earliest in the recorded asking order is asked. A follow-up rule is never overridden by a
   chooser.
8. **Selection step 2, the recorded order.** When no follow-up rule applies and no chooser acts, the
   earliest eligible question in the recorded order is asked. No model is called for the selection
   and no counting rule takes part. Whether a chooser is called is decided outside this
   specification. When one acts, this step does not choose.
9. **The path stays open.** The record of each asked question names which step chose it: `follow-up
   rule`, `recorded order`, or a value left for the routing specification. Selection accepts a
   chooser's returned identifier only if that question is eligible. Nothing here forbids a chooser
   being called between items 7 and 8.
10. **Update before the next question.** When an answer exposes an unforeseen issue, adds a
    requirement, or a chooser reports the set insufficient, the text model updates the analysis and
    that update completes before any further question is selected. A failed or part-way update is
    recorded and leaves the previous set in place. No question is selected until an update completes.
    A completed update keeps the identifier of every question it does not change.
11. **Behaviour left undefined does not resolve.** An answer that leaves behaviour undefined, such as
    "handle errors gracefully", does not resolve its question. The question stays pending and
    follow-ups continue until the user has made a decision whose outcome can be observed.

## Boundaries

- No chooser, no decisions-model call and no choice among eligible questions by judgment. That is D1
  step 3 and the routing specification.
- No classification of free-text answers, no conflict flagging, and no off, observe or act switches
  (D2, D3).
- No brief writing, fidelity review, readiness check or confirmation (D5, section 12).
- No metrics or evaluation reporting (D4) and no counting of calls beyond what item 9 records (D6).
- No change to the existing triage transport, and no change to the branch writer or spec writer
  (including T1).
- No confidence threshold, question limit or time limit stands in for the user's decision.
- No decision from D1 to D6 is changed or reopened.
