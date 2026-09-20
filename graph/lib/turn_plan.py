"""What the lanes take. Split from `turn.py` at the 200-line cap.

A slicer call can run for two hours, and it used to run beside the lanes of
every turn so that they were not held up by it. There is no such call in a
build turn any more — the plan phase is its own command (`lib/plan_phase.py`)
and a turn only builds — so what is left here is the one choice of cards.
"""

from __future__ import annotations

from backlog_status import is_live, runs_alone


def taking_now(ready: list[dict], args, started: int = 0) -> list[dict]:
    """The cards a turn runs, chosen once from what is startable.

    One place picks them, and one only: two lists picked in two places drift,
    and an evidence card in the middle of the queue was once protected while the
    third code card behind it was built.
    """
    # A live card reserves nothing in a code turn: it runs alone anyway, and its
    # files would otherwise keep a safe lane empty.
    if ready and not is_live(ready[0]):
        ready = [row for row in ready if not is_live(row)] or ready
    if not ready:
        return []
    # A live card acts on one shared stack, so it runs alone; code cards run
    # side by side, each in its own worktree, up to args.lanes.
    # Three at most: the keeper rebuilds a commit whose branch moved under it
    # three times before it gives up, so a fourth lane would turn ordinary
    # branch movement into a lane failure.
    # A lane is for a CODE card. A live card and a no-files evidence card
    # both run alone (backlog_status.runs_alone) — for two different
    # reasons — rather than holding a lane.
    lanes = max(1, min(3, args.lanes)) if not runs_alone(ready[0]) else 1
    taking = [row for row in ready if not runs_alone(row)][:lanes] if lanes > 1 else ready[:1]
    if args.max_tasks:
        taking = taking[:max(0, args.max_tasks - started)]
    return taking
