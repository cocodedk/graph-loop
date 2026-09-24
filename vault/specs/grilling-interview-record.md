---
status: spec
---

## Needs

- [[vault/01-grilling-interview.md]]

## Goal

Given an initial brief, interview the user one question at a time until every consequential
question is resolved, and keep an exact record of the session. This implements sections 4, 6,
8, 9 and 11 of `docs/rfc/grilling-stage.md`, and decisions **D5** and **D6** in
`docs/rfc/grilling-stage-decisions.md` (revision 3). It contradicts no decision in that file.

In scope: putting questions, recording answers, deciding when a question is resolved,
superseding decisions, reopening work after a change, the session record, and resuming.

Out of scope, and belonging to other specifications: how the next question is chosen (D1,
D3), who interprets an answer, and the choice of a model or service. This specification
requires no particular interpreter.

## Acceptance

Each item can be checked by reading the session record or the questions shown to the user.

**Asking**
1. Only one question is put to the user at a time.
2. Each question shown names three things: the uncertainty, the different readings, and the
   consequence of leaving it open.

**Recording answers**
3. A picked choice is recorded as picked.
4. A free-text answer is stored word for word. Its interpretation, and any confidence
   reported with it, is stored beside it and never in place of it.

**When a question is resolved (D5)**
5. A question becomes resolved only by (a) an answer that answers it, (b) a bounded
   delegation, or (c) an exclusion from scope.
6. These replies are recorded word for word and leave their question pending: a reply that
   answers only part, an unclear reply, a reply that may contradict an earlier decision,
   "I don't know", a skip, and no answer.
7. A reply that fits no known alternative, a malformed reply, and an unavailable interpreter
   each leave the question pending. None of them marks a question resolved.
8. When a reply may contradict an earlier decision, the user is shown the possible
   contradiction. The earlier decision stays current until a later resolved decision on the
   same question supersedes it.
9. Any resolved decision, whether an answer, a delegation or an exclusion, can be superseded
   by a later resolved decision on the same question. The superseded decision stays in the
   record word for word and names the decision that superseded it. It is never current.

**Completeness and later changes**
10. When no question is left in the queue, a completeness review starts. The empty queue does
    not end the interview by itself.
11. A question raised later goes into the same record.
12. A settled decision is not asked again unless there is new evidence or a changed
    requirement, and the record names which of the two it was.
13. When a confirmed decision is changed, the decisions that depend on it are marked for
    review in the record.

**The session record**
14. The record holds: exact questions and answers; interpretations with any confidence;
    revisions and superseded decisions; and review findings.
15. For every turn the record holds three separate counts (D6): text-model calls;
    decisions-model requests made to interpret the answer; and decisions-model requests made
    to choose the next question.
16. Every request actually made is listed, with its purpose, its outcome and its timing, and
    with its cost where one is available. Retries and requests that failed, timed out or came
    back invalid are listed and counted like any other. The counts equal what was spent, not
    what succeeded.
17. A turn with zero text-model calls is a routine turn, and the record shows this. A routine
    turn may hold more than one interpretation request when a later check depends on an
    earlier result. Each such request is counted under its own purpose.

**Resuming and keeping apart**
18. After an interruption, the session resumes without asking again any question the record
    shows as resolved.
19. The record is kept apart from the decisions that later stages plan from. Nothing in the
    record, including a pending reply or a superseded decision, is handed to a later stage
    as a current decision.

## Boundaries

- No rule is set here for choosing the next question, and none for who or what interprets an
  answer. No interpreter, model or service is required or named. D1 and D3 belong to other
  specifications.
- No confidence value is treated as user intent, as authority, or as proof of completeness
  (section 9). No confidence threshold is set here.
- This does not compose the agreed brief, review it, or confirm it (sections 11 to 12 and
  D5's brief checks), and it does not start branches, specifications, task cards or
  execution. Confirming a brief is not granted here.
- This does not evaluate the workflow or report the measures of section 14 (D2, D4).
- This does not change the existing triage transport in `graph/lib/provider_jev.py`.
- This does not change the branch writer or the spec writer, and does not add a log for their
  reviewers (task T1).
- This adds no runtime dependency (PyYAML stays the only one). It carries no account name,
  machine path, foreign commit hash or task identifier from private work.
- Nothing here permits changing `docs/rfc/grilling-stage.md` or
  `docs/rfc/grilling-stage-decisions.md`. A change to a decision needs a new revision and a
  new owner confirmation.
