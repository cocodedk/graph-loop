"""Asking Jev which cause explains one failed ending, and when to ignore it.

The rung sits in FRONT of the plan belt rather than on it. The belt stops at the
first resource that answers, so an answer it could not read would have ended every
unknown as unknown; in front, an unreadable answer returns nothing and the text
belt decides exactly as it did before Jev existed.

`unknown` is one of the seven causes, but it is not one of the six this rung will
act on. It means "not enough evidence", which is the absence of a cause: taking it
as a verdict would spend the card's one model chance on a shrug and, because
`triage_routes` reads an unknown on an exhausted task as "unknown twice", page a
person a round early. It stays in the question, because both models must be asked
the same thing, and it falls through to the paid text call.
"""

from __future__ import annotations

from provider_jev import MODEL, ask, question
from triage_evidence import OUTCOMES, Ending
from triage_signatures import VERDICTS, Decision

# The seven causes with the words they are judged by, written once: the text prompt
# builds its sentence from this table, so the two models are asked one question.
#
# Each is worded as what the loop does next, because that is the only thing the
# verdict decides: work and contract make the card a wall the slicer re-cuts
# (`backlog_status.is_wall`), gate, rig and environment raise a repair
# (`triage_routes.MECHANICAL`), harness is the loop's own to fix. Four-word labels
# ("the check is wrong") left both models to guess whose check, and both blurred a
# fence refusal into one. Measured on the six recorded endings, 2026-09-19: Jev
# went from 3 of 6 right to 5 of 6, the text call from 3 of 6 to 5 of 6.
CAUSES = {
    "work": "the card asks for the wrong thing, or for too much; it must be cut again",
    "contract": "the card's own terms are wrong - the files it grants, what it names, "
                "what it promises; it must be cut again",
    "gate": "the check this card runs is wrong or cannot run; the check must be repaired",
    "rig": "the test support is wrong - a fixture, a helper, the way tests are run; "
           "the support must be repaired",
    "environment": "the machine is missing something the work needs, rather than the "
                   "loop withholding it; the machine must be repaired",
    "harness": "the loop's own code or a provider did this to a card that was fine; "
               "the loop must be fixed",
    "unknown": "the evidence here does not say",
}
DECIDING = tuple(name for name in VERDICTS if name != "unknown")
NOTES = 1200


def evidence(ending: Ending) -> dict:
    """The few facts the choice turns on, and nothing else.

    Measured on the six recorded endings, 2026-09-19: handed the whole record and
    every artifact, Jev named the cause the report names on 1 of 6 and gave two
    different causes across repeats on 2 of 6. Handed this, it is 3 of 6 and gives
    the same cause five times out of five on all six. Same question, same price;
    only the evidence is smaller. So the text call keeps the whole record, which
    it reads better, and this keeps the facts, which Jev reads better.
    """
    step, said = _stopped(ending)
    return {
        "how_it_ended": ending.card.get("status"),
        "the_step_that_stopped_it": step,
        "what_it_said": said,
        "files_the_card_granted": list(ending.card.get("files") or [])[:50],
        "the_card_s_check_was_run": any(row.get("step") == "gate"
                                        for row in ending.events),
        "notes": _notes(ending),
    }


def _stopped(ending: Ending) -> tuple[str, str]:
    """The step that stopped this ending, and what it said.

    NOT the last event. An ending's last event is `released`, which carries
    neither a step nor a message, so on every real ending Jev was handed the two
    fields this question turns on empty — and answered `unknown` on all five of
    campaign 7's, or guessed from the tail of the artifacts.

    It is the ending's own OUTCOME (`triage_evidence.OUTCOMES`) that says what
    stopped it, and nothing else: merely the last message would be the push
    alert on a healthy ending, which stopped nothing. An outcome with no message
    stopped nothing either, and says so with two empty fields rather than a
    guess. `rebuild_queued` names no step, so the step is then the last one the
    lane entered before it.
    """
    ends = [index for index, row in enumerate(ending.events)
            if row.get("kind") in OUTCOMES and row.get("why")]
    if not ends:
        return "", ""
    stopped = ending.events[ends[-1]]
    steps = [row.get("step") for row in ending.events[:ends[-1] + 1] if row.get("step")]
    return str(stopped.get("step") or (steps[-1] if steps else "")), str(stopped["why"])


def _notes(ending: Ending) -> str:
    """What the step produced, bounded, tail first: that is where a failure lands,
    and it is where `triage_evidence.words` already cuts."""
    said = ""
    for texts in ending.artifacts.values():
        for piece in texts:
            said = (said + "\n" + piece)[-NOTES:]
    return said.strip()


def rung(state: dict, space, label: str) -> Decision | None:
    """Jev's cause for this ending, or nothing, which leaves it to the text belt."""
    out = call(state, CAUSES, DECIDING, space, label)
    if not out.ok or out.verdict not in DECIDING:
        return None
    return Decision(out.verdict, "jev", f"{out.text} ({CAUSES[out.verdict]})"[:400])


def call(state: dict, criteria: dict, allowed: tuple, space, label: str, **options):
    """One prepared question, with the same artifacts and accounting as triage."""
    body = question(state, criteria, **options)
    with space.step(label, "jev_call") as note:
        out = ask(body, allowed)
        note(outcome=out.kind, cost=out.cost, tokens=out.tokens, on=MODEL)
    space.artifact(label, "jev-question", body)
    space.artifact(label, "jev-answer", out.raw or out.text)
    # `plan` is the account planning and triage calls file under, so the doctor does
    # not grade this as a builder answer that was thrown away (`doctor_spend`).
    space.attempt(label, account="plan", kind=out.kind, cost=out.cost,
                  tokens=out.tokens, purpose="triage")
    return out
