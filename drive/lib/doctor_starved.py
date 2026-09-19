"""The complaint the board could not make: a queue with work in it and nothing to start.

The loop sat idle from 22:52 to 23:25 on 2026-08-30 with fifteen todo cards and a
live driver, and `--check` said "no red flags", because every one of those cards
waited on a handful the loop had already handed back. Nothing was broken; nothing
could move either. Starvation is the one failure that looks exactly like health.
"""

from __future__ import annotations

from backlog import settled
from backlog_status import spent_its_rounds
from doctor_types import Complaint


def check_starved(tasks: list[dict], claimed: int) -> list[Complaint]:
    """Todo work that nothing can reach, while no lane is busy."""
    if claimed:
        return []                      # a lane is working: the queue is not the problem
    # The same answer the picker uses, or the board reports a starved queue that
    # is not one: a sliced or dropped need is satisfied.
    done = settled(tasks)
    waiting, blockers, spent = [], set(), []
    for task in tasks:
        if task.get("status") != "todo" or task.get("blocked_by_human"):
            continue
        if spent_its_rounds(task):
            # The picker will not offer it. Said here, or it is a todo card
            # nothing will ever pick and the board calls the queue healthy.
            spent.append(task.get("id"))
            continue
        unmet = {need for need in (task.get("needs") or []) if need not in done}
        if unmet:
            waiting.append(task.get("id"))
            blockers |= unmet
        else:
            return _spent(spent)       # something is ready; the spent ones still need saying
    if not waiting:
        return _spent(spent)
    named = ", ".join(sorted(str(blocker) for blocker in blockers)[:6])
    return _spent(spent) + [Complaint(
        "the queue", f"{len(waiting)} todo cards and none can start — every one waits on {named}",
        "fix or re-slice those cards; the loop has nothing to do until one of them is done")]


def _spent(spent: list) -> list[Complaint]:
    if not spent:
        return []
    return [Complaint("the queue", f"{', '.join(str(one) for one in spent[:6])} "
                      "has spent every rebuild round, so the picker will not offer it",
                      "re-slice it or drop it; leaving it todo hides it from the board")]
