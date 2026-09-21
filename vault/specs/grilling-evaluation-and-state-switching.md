---
status: spec
---

## Needs

- [[vault/01-grilling-interview.md]]

## Goal

Implements D2, D3 and D4 of `docs/rfc/grilling-stage-decisions.md` and contradicts none of them. It covers evaluation of the grilling stage (RFC sections 9 and 14) and the switching of the decisions model's states.

Evidence comes from recorded interviews replayed offline and from the records observe mode leaves in live interviews. Either becomes a reviewed example once a reviewer has annotated it in a format this work defines. The same interviews can be run entirely by the text model as the baseline. A person switches states. The live interview reads those recorded switches.

## Acceptance

1. The evaluation runs with no network and no paid calls when given recorded answers and recorded model replies. A run that tries a network or paid call fails.
2. A reviewer annotation format is defined and documented. A recorded interview or an observe-mode record with an annotation is a reviewed example. One without an annotation is still counted, as an example with no annotation.
3. Waiting time per answer (slow turns included), total model cost where recorded, and a resolved question asked again are computed from the record alone. Where cost is not recorded, the report says so.
4. Unnecessary questions, questions incorrectly marked answered, contradictions missed, decisions lost or altered in the brief, and gaps found by the final reviewer are computed only from annotations. Where no annotation exists the report says "not annotated", never zero.
5. Text-model calls avoided is reported only against a text-model-only run of the same interview. Without one the report says "no baseline".
6. For each kind of answer and for the chooser, the report shows how many reviewed examples it holds, how many of the model's results disagreed with the reviewed decision and which, and how many examples carry no annotation.
7. Switching a state is a recorded decision by a person. Observe needs no report. Switching to act, for a kind of answer or for the chooser, requires naming an evaluation report. The tool refuses when that report holds no reviewed example of that kind or of the chooser. A report with at least one reviewed example is accepted. No acceptability threshold is built in, and the refusal message does not claim the category is reliable.
8. A test with a scripted live interview shows two things. A kind not switched to act goes to the text model, and the model's result is kept only as a record and cannot resolve the question. A kind switched to act is acted on: for a routine classification (an answer that fits a known alternative, resolved without conflict, new requirement or uncertainty), the turn makes no text-model call. Conflicts, new requirements and uncertain interpretations still go to the text model even when the kind is on act.
9. A confidence threshold, where a person chooses one, is recorded together with the report and the examples it was set from. The tool refuses a threshold whose named report does not contain those examples.
10. Tests cover interrupted sessions, unexpected answers, changed decisions, unavailable model calls, malformed responses, and attempts to finish with pending questions. An invalid, malformed or unavailable model result never marks a question resolved. Finishing with a pending question is refused.
11. All states start off. Each state (off, observe, act) is set separately for interpreting answers and for choosing the next question.

## Boundaries

- Not granted: any built-in acceptability threshold, or any claim that a nonempty report proves a category reliable. Reliability stays the person's judgment.
- Not granted: switching to act without a named report, or switching to observe on the tool's own initiative.
- Not granted: a model's result resolving a question for a kind not on act, or after an invalid or unavailable response.
- Not granted: reporting an unannotated judgment measure as zero, or reporting calls avoided without a text-model-only run.
- Not granted: network access, paid calls, or a new runtime dependency beyond PyYAML in the evaluation.
- Not granted: changes to D1, D5, D6 or task T1 of the decisions document, or to the RFC text.
- Not granted: tracked files that name any local account, path, machine or foreign identifier (`scripts/scrub-check.sh` must pass).
- Files stay under 200 lines and `ruff check .` passes.
