---
status: spec
---

## Needs

- [[vault/02-agreed-brief-review.md]]

## Goal

Turn the recorded decisions of a grilling interview into one agreed brief. A reviewer separate from the writer checks it. The user confirms one named revision. That revision is handed explicitly to branch writing and specification. This follows `docs/rfc/grilling-stage.md` sections 11, 12 and 13.

This specification implements D5 in `docs/rfc/grilling-stage-decisions.md` and contradicts none of D1 to D6. D5 says a decision is a question the user has resolved by an answer, a bounded delegation or an exclusion. A reply that answers only in part, is unclear, or may contradict an earlier decision stays pending. A decision that a later resolved decision on the same question supersedes is never current.

The fidelity checks of the review are another specification's work. This one covers the brief, the reviewer's inputs and findings, readiness, confirmation, and the handoff.

## Acceptance

1. The brief holds the outcome, scope, the current resolved decisions, examples, constraints, exclusions and explicitly delegated choices. Each decision carries a stable identifier that does not change between revisions. Look at any brief to check this.
2. The brief holds no pending reply and no superseded decision as a decision. Build a session with one pending question and one superseded decision. Neither appears in the brief as a decision.
3. The reviewer is a separate call from the writer. Its recorded inputs are the original request, the recorded decisions and the evidence. Its inputs do not include the writer's own reasoning.
4. Every blocking finding names the decision concerned and states its consequence. A finding that says only "needs more detail" is not accepted as a finding.
5. The brief is reported not ready in each of these cases: a consequential question is pending in the sense of D5, a contradiction remains, acceptance cannot be observed, or the review has a blocking ambiguity. A time limit, a question limit, an empty queue or high confidence from a decisions model never turns a not-ready brief into a ready one. Show each case with a run where only that condition is present.
6. The user confirms one named revision of a brief that is ready. Confirming a revision that is not ready, or one that names no revision, is refused. Confirming starts no execution and approves no campaign. After a confirmation, no run and no campaign approval exists that did not exist before.
7. The confirmed brief and its revision are passed as their own input to the branch writer, the spec writer and their reviewers, and not only inside a goal string. Show that each of the four receives the brief and its revision as a separate input. Raw transcripts and rejected drafts are not among the inputs.
8. Any change to a confirmed revision needs a new readiness check and a new confirmation. It also needs a new review of the material that depends on what changed. This holds whether the change is to a decision or to any other content of the brief. Change one decision, then change one non-decision item such as an example. In each case the earlier confirmation no longer counts for the changed revision. The changed revision is not handed on until readiness, the dependent review and a new confirmation are recorded.
9. A specification written from a confirmed brief names the decision identifiers it implements. A specification that names none is refused.

## Boundaries

- Not granted: starting execution, approving a campaign, or treating a confirmation as either.
- Not granted: handing over raw transcripts or rejected drafts.
- Not granted: readiness from a time limit, a question limit, an empty queue or a decisions model's confidence.
- Not granted: changing D1 to D6, or the meaning of "decision" in D5.
- Not in scope: the fidelity checks of the review, which are another specification's work.
- Not in scope: the interview itself, including question definitions, the decisions model and its fallback.
- Not in scope: changing triage's existing contract or the shared transport.
- Not granted: a new runtime dependency, or a new configuration name beyond `GRAPH_REPO`, `GRAPH_HELPER`, `GRAPH_PROVISION_COPY` and `GRAPH_PROVISION_LINK`.
- Nothing local travels: no account name, home directory, machine path, foreign commit hash or task identifier from private work goes into any tracked file.
