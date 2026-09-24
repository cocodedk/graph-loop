"""Ask, and on a refusal ask again with the refusal fed back.

The slicer has had this since it was written: three rounds, the validator's
own words appended to the prompt, and only then a refusal that costs the whole
call. The branch writer and the speccer asked ONCE, so a single malformed
answer — from the planner or from its reviewer — threw the layer away, paid
planner call and all. Two of six branches died that way on the first real run:
one reviewer answered `{"review":"REJECT","accept":true}`, a contradiction the
parser rightly refuses, and one planner answered text that was not YAML
(2026-09-18).

One home, because three copies of a retry loop drift into three different
numbers of rounds.
"""

from __future__ import annotations

from collections.abc import Callable

ROUNDS = 3
# States a repair round can fix, from every layer that has an independent
# reviewer: the branch writer's and the speccer's `review_refused`, and the
# slicer's `coverage_refused` and `progress_refused`. A reviewer names what is
# wrong in words the planner can act on, exactly like the validator's. All four
# were returned as finished states, so they ended the layer on the spot and
# those words were thrown away (2026-09-18, the second campaign run).
#
# What is NOT here: `review_unavailable`, because nobody read the answer, and
# `needs_person`, because it is a true answer rather than a bad one.
REPAIRABLE = ("review_refused", "coverage_refused", "progress_refused")

# What every refusal ends with, wherever it is fed back. The second sentence is
# the expensive half: told only to "return one corrected answer", a planner
# rewrites the whole answer from memory to fix one key and drops another that
# was already right. One plan phase spent round 3 that way, having got `needs`
# right in rounds 1 and 2 (2026-09-18).
AGAIN = ("\nReturn one corrected answer in the same closed shape. Change only what was "
         "refused; every other key stays exactly as you wrote it.")


class Unreachable(Exception):
    """No resource answered at all. Not a bad answer, so no round is spent and
    asking again asks the same question of the same silence."""


def repaired(question: str, ask_once: Callable[[str], str],
             write: Callable[[str], tuple[str, object]],
             *, rounds: int = ROUNDS) -> tuple[str, object]:
    """Ask `ask_once`, hand its answer to `write`, and on a refusal ask again.

    `ask_once(question)` returns the answer text or raises. `write(answer)`
    returns the caller's own `(state, detail)` pair, or raises `ValueError`
    when the answer is not the closed shape — which is the one thing a repair
    round can fix, because the model is told exactly what was wrong with what
    it wrote. Every other error is the caller's to handle: an unreachable
    planner is not a bad answer, and asking it again asks the same question.

    A `(state, detail)` pair whose state is in `REPAIRABLE` is a refusal too,
    not a finished answer: the independent reviewer read the answer and said
    what was wrong with it. It is fed back the same way and returned as it
    stands once the rounds are spent.

    The last round's refusal is raised, not swallowed: a caller that reported
    "refused" without saying what was wrong sent whoever ran it back to the
    logs.
    """
    asked = question
    for round_number in range(1, max(1, rounds) + 1):
        answer = ask_once(asked)
        last = round_number >= max(1, rounds)
        try:
            state, detail = write(answer)
        except ValueError as refusal:
            if last:
                raise
            why = str(refusal)
        else:
            if state not in REPAIRABLE or last:
                return state, detail
            why = str(detail)
        asked = question + "\n\nThat answer was refused: " + why + AGAIN
    raise AssertionError("unreachable: the loop returns or raises")   # pragma: no cover
