"""The campaign's own source gap: when it may be sliced again, and how a
campaign ends when it may not.

The slicer stops trying the gap after an answer that asked for a person, or
after three answered failures, and nothing but a new `sources_declared` starts
it again. It is not a wait for a person (astra's section H 5): a stopped gap
ends the campaign honestly, and declaring a source is how the work resumes.

Ending honestly is not finishing. `dropped` settles a dependency; it does not
prove the requirement, so an exhausted source gap gets its own terminal result —
`ended_with_gaps`, exit 78 — recording the sources, a digest of the backlog it
left and the gap that was named. Nothing here ever writes `sources_declared`: a
fabricated declaration is the loop telling itself the sources moved.

Split from `slice_turn.py`, which was at the 200-line cap. How the
campaign ENDS with those gaps — the receipt and its reader — is `source_ended`,
split off at that same cap; the names are re-exported here, so this file stays
the one door.
"""

from __future__ import annotations

from finishing import SOURCE_GAP
from replan import MAX_REPLANS
from slice_outcome import UNANSWERED
from source_ended import (  # noqa: F401 — the door stays here
    ENDED,
    end_on_unproved_work,
    end_with_gaps,
    ended,
)

STOPPERS = ("slice_needs_person", "slice_gap_capped")


def may_try(space) -> bool:
    """Whether the source gap may be sliced now.

    A stop stands until the sources move. Nothing lifts it from inside the
    loop: the decider's requeue used to buy one more attempt, and with the
    decider cut there is no such buyer — a declared source opens a new window
    (`_last_start`), and a campaign that gets none ends with its gaps named.
    The cap is recorded here, once per window, because the count is what
    reaching it means.
    """
    events = space.events()
    start = _last_start(events)
    if _last_stop(events, start) is not None:
        return False
    failures = _failures(events, start)
    if len(failures) < MAX_REPLANS:
        return True
    # Said once: the board is how anyone SEES this, never a handoff
    # (CLAUDE.md § Code).
    space.event("slice_gap_capped", task=SOURCE_GAP, count=len(failures))
    space.alert(SOURCE_GAP, f"the source-gap slicer failed {len(failures)} times; "
                            "the campaign ends with this gap unless a source is declared")
    return False


def end_on_stopped_gap(space, book) -> dict | None:
    """End the campaign on a gap that stopped and was never reopened, or None
    while it may still be sliced.

    `may_try` asks this before a slice and records the cap when it is reached;
    this asks it after, when nothing is startable, and records nothing new. A
    stopped gap is the campaign's ending and nothing in the loop will cover it.
    Without this the driver returned 1 for ever on a gap stopped at
    `needs_person` — the plan phase had nothing left to plan, and the supervisor
    read the fifth quick exit as the driver dying (campaign 7).
    """
    stop = _last_stop(space.events(), _last_start(space.events()))
    if stop is None:
        return None
    end_with_gaps(space, book, "", {
        "why": "the source gap stopped and no source has been declared since",
        "gap": str(stop[1].get("why") or "")})
    return ended(space)


def _last_start(events: list[dict]) -> int:
    """Where this window opens: the sources were declared, or a gap slice
    actually worked. Both make everything before them history."""
    return max([index for index, row in enumerate(events)
                if row.get("kind") == "sources_declared"
                or (row.get("kind") == "slice_finished" and row.get("task") == SOURCE_GAP
                    and row.get("rc") == 0)] or [-1])


def _failures(events: list[dict], start: int) -> list[dict]:
    """Answered failures of the gap slice in this window. A provider refusal is
    not one: nobody judged the sources."""
    return [row for row in events[start + 1:]
            if _answered(row) and row.get("rc") not in (0, None)]


def _answered(row: dict) -> bool:
    """Whether this row is the gap slice ANSWERING. A call nobody reached — a
    provider refusal — judged nothing, so it neither counts towards the cap nor
    spends the attempt a requeue bought (a lesson: a review or a build that did
    not happen is a harness fault, never a finding). A call that ran out of time
    is not one of those: it read the question and paid for planner calls of its
    own, and free, it repeated every turn (astra round 4, finding 8)."""
    return (row.get("kind") == "slice_finished" and row.get("task") == SOURCE_GAP
            and row.get("state") not in UNANSWERED)


def _last_stop(events: list[dict], start: int) -> tuple[int, dict] | None:
    """The newest ending that stops the gap in this window, with where it is."""
    stops = [(index, row) for index, row in enumerate(events)
             if index > start and row.get("kind") in STOPPERS
             and row.get("task") == SOURCE_GAP]
    return stops[-1] if stops else None

