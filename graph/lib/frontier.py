"""What can start now, asked of a list of cards rather than of a file.

Split from `backlog.py` at the 200-line cap, and because the projection into
waves (`waves.py`) has to ask the same question of cards it has written
nowhere: it treats a wave as done and asks again. Two readings of "what may
start" drift — the picker and the board disagreed about a starved queue once
already (`backlog_status`) — so the rule lives here and `Backlog.ready` and
`Backlog.startable` stay its front door.
"""

from __future__ import annotations

from backlog_reach import overlap, reach
from backlog_status import RUNNABLE, settled, spent_its_rounds


def ready(rows: list[dict]) -> list[dict]:
    """Every card whose status is todo and whose needs are all done.

    Held cards stay in the list: the caller has to see that they are next and
    waiting, rather than have them silently skipped.
    """
    done = settled(rows)
    out = []
    for row in rows:
        if row.get("status") != RUNNABLE:
            continue
        if spent_its_rounds(row):
            continue          # its rounds are spent: offering it again buys a fourth
        if set(row.get("needs") or []) <= done:
            out.append(row)
    return out


def first_of(rows: list[dict], task_id: str) -> dict:
    """The row a task id stands for: the FIRST of that id, which is what
    `Backlog.task` answers and therefore what every part of the loop that
    RUNS a card reads — the lane, the keeper, the scope check.

    A backlog can hold an id twice; `startable` already guards against
    offering both. Reading the last one here reserved one row's paths while a
    lane edited another's, and offered a card already running a second lane.
    """
    for row in rows:
        if row.get("id") == task_id:
            return row
    return {}


def startable(rows: list[dict], running: list[str] | None = None) -> list[dict]:
    """Ready, not held for a human, and not reaching a path another card holds."""
    held = set()
    for task_id in running or []:
        held |= reach(first_of(rows, task_id))
    out, taken = [], set()
    for row in ready(rows):
        if row.get("blocked_by_human"):
            continue
        if row.get("id") in taken:
            continue          # one card per id in a turn: two lanes would share a claim
        taken.add(row.get("id"))
        touches = reach(row)
        if overlap(touches, held):
            continue
        held |= touches
        out.append(row)
    return out
