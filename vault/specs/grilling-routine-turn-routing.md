---
status: spec
---

## Needs

- [[vault/01-grilling-interview.md]]

## Goal

Route the routine turns of the grilling interview without a text-model call.
This implements D1 step 3, D3 and D6 of `docs/rfc/grilling-stage-decisions.md`
and contradicts none of them. It follows sections 3, 6, 7, 9, 10 and 13 of
`docs/rfc/grilling-stage.md`.

The decisions model is reached through the transport `graph/lib/provider_jev.py`
already holds. Its part is in one of three states: off, observe or act. The state
is set separately for interpreting answers and for choosing the next question.
Everything is off until a person's recorded decision switches it. Observe needs
no evaluation report. Act is per kind of answer and for the chooser, and needs
the report-backed decision of D2, which the evaluation specification owns.

## Acceptance

Each item can be observed in a turn's record or in the questions asked.

1. With interpreting off, no interpretation request is made. With the chooser
   off, no selection request is made. A fresh setup has both off.
2. With interpreting in observe or act, the model is given the current question,
   the user's exact answer, the prepared alternatives, the recorded decisions and
   the evidence. Its result is recorded in two parts. The first is which prepared
   alternative the answer matches, or none. The second is the kind of answer, one
   of: answers the question, answers only part, may contradict a recorded
   decision, introduces a new requirement, unclear.
3. A result of a kind not switched to act goes to the text model. It cannot
   resolve the question by itself. It is kept as a record beside the text
   model's interpretation.
4. For a kind switched to act: "answers the question" records the interpretation
   as provisional and continues. "Answers only part" shows the prepared
   follow-up naming that alternative when one exists, and otherwise asks the text
   model for one. The other three kinds always go to the text model.
5. A chooser request is made only when no deterministic rule applies, more than
   one question is eligible, and the chooser's state is observe or act. With the
   state off, no request is made.
6. A chooser request is given every eligible question's identifier, wording,
   consequence and dependents, section 10's four criteria, and the recorded order
   with its reasons. It returns one eligible identifier, or reports the set
   insufficient.
7. In act, the identifier the chooser returns is the question asked. In observe,
   the recorded order still decides what is asked, and the chooser's choice is
   only recorded beside it.
8. In act, a report that the set is insufficient goes to the text model to
   update the analysis. In observe, that report is only recorded. No text-model
   call is made because of it, and the turn runs exactly as it would with the
   chooser off.
9. In act, an invalid or unavailable chooser reply falls back to the recorded
   order, and the fallback is recorded. In observe, such a failure is recorded
   and changes nothing. Neither case makes a text-model call because of the
   failure.
10. Any invalid or unavailable response to an interpretation request, any
    uncertain interpretation, and any result outside the prepared set returns
    control to the text model. None of them marks a question resolved.
11. Every turn records three separate counts: text-model calls, interpretation
    requests and selection requests. A routine turn has zero text-model calls,
    any number of interpretation requests, and at most one selection request.
12. Independent checks about one answer share one request. A dependent check is
    a later request under its own purpose.
13. Every request actually made is counted and recorded with its purpose,
    outcome and timing. This includes retries, failures, timeouts and invalid
    replies.
14. The model's confidence is recorded with the interpretation. It is not treated
    as the user's intent, and no universal threshold is assumed.
15. If transport is factored out of `provider_jev.py`, triage's existing contract
    and tests pass unchanged.

## Boundaries

- Not granted: switching any state to observe or act. That takes a person's
  recorded decision.
- Not granted: act for any kind of answer or for the chooser without the
  report-backed decision of D2. The evaluation specification owns that report
  and this one does not produce it.
- Not granted: letting a decisions-model result, confidence included, resolve a
  question by itself or stand in for the user's intent.
- Not granted: any change to D1 to D6 of the decisions file. A change needs a new
  revision and confirmation.
- Not granted: changing triage's contract or tests.
- Not granted: any other use of the decisions model. Discovery, unfamiliar
  answers, brief composition and final review stay with the text model and the
  existing independent review.
- Not granted: a new runtime dependency, or any name of a particular project
  added to the loop's configuration.
