"""What the lanes take. Split from `turn.py` at the 200-line cap.

A slicer call can run for two hours, and it used to run beside the lanes of
every turn so that they were not held up by it. There is no such call in a
build turn any more — the plan phase is its own command (`lib/plan_phase.py`)
and a turn only builds — so what is left here is the one choice of cards.
"""

from __future__ import annotations

from backlog_status import is_live, runs_alone

# Three at most, whatever anybody asks for: the keeper rebuilds a commit whose
# branch moved under it three times before it gives up, so a fourth lane would
# turn ordinary branch movement into a lane failure. It is the loop's own
# ceiling, not a preference, and it is also `--lanes`' default.
MOST_LANES = 3


def code_first(ready: list[dict]) -> list[dict]:
    """What a code turn is really choosing among.

    A live card reserves nothing in a code turn: it runs alone anyway, and its
    files would otherwise keep a safe lane empty. The picker and the recorder
    both start here, or the record describes a turn that did not happen.
    """
    if ready and not is_live(ready[0]):
        return [row for row in ready if not is_live(row)] or ready
    return ready


def lane_cap(ready: list[dict], args) -> int:
    """How many lanes this turn may use, and the one place that says so.

    One for a card that runs alone; otherwise the smallest of what was asked
    for and the keeper's ceiling. The recorder below and the picker read the
    same answer, because a cap read twice is a cap that can disagree with
    itself in the record.
    """
    if not ready or runs_alone(ready[0]):
        return 1
    return max(1, min(MOST_LANES, args.lanes))


def width_against_lanes(space, ready: list[dict], taking: list[dict],
                        args, turn_id: str) -> dict:
    """Record what the graph offered this turn against what the loop could run.

    Here, because these three numbers are this module's own decision: the
    width it was given, the cap it applied and the cards it handed back. Read
    anywhere else they are a second opinion, and `report` names the turns
    where the graph was wider than the loop from this record alone.
    """
    offered = code_first(ready)
    return space.event("turn_lanes", turn=turn_id, width=len(offered),
                       cap=lane_cap(offered, args), lanes=len(taking))


def taking_now(ready: list[dict], args, started: int = 0) -> list[dict]:
    """The cards a turn runs, chosen once from what is startable.

    One place picks them, and one only: two lists picked in two places drift,
    and an evidence card in the middle of the queue was once protected while the
    third code card behind it was built.
    """
    ready = code_first(ready)
    if not ready:
        return []
    # A live card acts on one shared stack, so it runs alone; code cards run
    # side by side, each in its own worktree, up to the cap.
    # A lane is for a CODE card. A live card and a no-files evidence card
    # both run alone (backlog_status.runs_alone) — for two different
    # reasons — rather than holding a lane.
    lanes = lane_cap(ready, args)
    taking = [row for row in ready if not runs_alone(row)][:lanes] if lanes > 1 else ready[:1]
    if args.max_tasks:
        taking = taking[:max(0, args.max_tasks - started)]
    return taking
