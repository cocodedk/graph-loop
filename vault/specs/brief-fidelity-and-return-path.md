---
status: spec
---

## Needs

- [[vault/02-agreed-brief-review.md]]

## Needs

- [[vault/02-agreed-brief-review.md]]

## Goal

Implements decision **D5** in `docs/rfc/grilling-stage-decisions.md` (revision 3, confirmed by the owner). It contradicts none of D1–D6.

Two things are added to the agreed-brief work. First, the independent review compares the brief with the current resolved decisions of the decision record, exactly as D5 defines them, and reports five kinds of blocking finding. Second, a later stage that finds a decision missing does not restart the interview. It records a precise question with the work it affects, carries on with unrelated work, and the question returns to the same decision record for a focused follow-up when a person is next present.

Terms are as D5 defines them:

- A decision is a question the user resolved by an answer that answers it, by a bounded delegation, or by an exclusion from scope.
- A reply that answers only part, is unclear, or may contradict an earlier decision is kept word for word and leaves its question pending. It is not a decision.
- Any decision, whether an answer, a delegation or an exclusion, can be superseded by a later resolved decision on the same question. The superseded decision stays in the session history word for word, names what superseded it, and is never current.
- "Current resolved decisions" are the decisions not superseded.

## Acceptance

Fidelity review:

- The review reports a blocking finding of each of these five kinds. Each finding names the decision and its consequence.
  1. **Unsupported:** a decision in the brief that no current resolved decision supports. This includes one supported only by a pending reply or only by a superseded decision.
  2. **Omitted:** a current resolved decision the brief leaves out.
  3. **Altered:** a current resolved decision the brief changes.
  4. **Contradiction:** the brief contradicts itself or a current resolved decision.
  5. **Ambiguous or unobservable:** behaviour left ambiguous, or acceptance that cannot be observed.
- A brief that correctly leaves out a superseded decision, or a pending reply, gets no finding for it.
- One recorded-decision set per case shows each of these outcomes:
  - **Revised answer:** the brief states the old answer and gets an unsupported finding. The brief states the new answer and gets none.
  - **Superseded delegation:** a brief that still grants the delegation gets an unsupported finding. A brief that leaves it out gets none.
  - **Partial reply:** a brief that states a decision from the partial reply gets an unsupported finding. A brief that leaves it out gets none, and its question stays pending, so the brief is reported not ready (D5).
- A superseded decision is still present word for word in the session history, names what superseded it, and is not treated as current by the review.
- Each of the five kinds can be shown to fail in a test: a brief with that fault gets that kind of finding.

Return path:

- When a later stage needs a decision that is missing from the record, it writes a question that names the missing decision and the work it affects.
- An unattended stage that records such a question does not restart the interview. The test observes that no already-resolved question is asked again, and that work not named as affected carries on.
- The recorded question is a pending question in the same decision record, not in a separate list. It is available for a focused follow-up when a person is next present, and while it is pending the brief is reported not ready (D5).
- A settled decision is not asked again in a follow-up unless the follow-up names new evidence or a changed requirement that gives a reason to revisit it. The test shows a follow-up that names neither, and the settled decision is reused.
- Earlier decisions stay available wherever they still apply. A follow-up can see the current resolved decisions of the record. A superseded decision is kept in the history and is not offered as current.

This adds to the agreed-brief specification. Every acceptance line of that specification still holds as written.

## Boundaries

- It does not change the acceptance of the agreed-brief specification. It only adds to it.
- It does not run the interview, classify answers, choose questions, or decide what counts as answering. It uses the decision states D5 defines.
- It does not decide product requirements. The reviewer and the writers are not granted that authority. Only the user's recorded decisions and confirmation are.
- It does not confirm a brief, start execution, approve a campaign, or change any card status.
- An unattended stage is not granted the right to answer, resolve or supersede a decision. It only records the question.
- It does not set a Jev confidence threshold, and it does not change how triage uses the Jev transport.
- It does not change D1–D4 or D6, and it does not add the reviewer and writer call logging that T1 retains.
- It adds no runtime dependency other than PyYAML. No file it adds exceeds 200 lines.
- No account name, home path, machine path or foreign identifier enters a tracked file.
