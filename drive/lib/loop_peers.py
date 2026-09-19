"""Which live cards wait while one live call is open, and when they stop waiting.

Split from `loop_steps` at the 200-line cap. The stack is one, so a live call
holds every other live card; the hold is written with a REASON, and the release
frees exactly the cards carrying that reason.
"""

from __future__ import annotations

from backlog_status import is_live


# The reason a hold carries while a call is running. The release frees cards by
# this exact text, so a hold written for another reason — a call that never came
# back, a person's decision — survives it. The TASK is in the text: a shared
# reason lets one runner's release free the holds the next runner just wrote.
def open_why(task_id: str) -> str:
    return f"a live call is open for {task_id} and its end is not recorded"


def lost_why(task_id: str) -> str:
    return (f"{task_id}'s live call did not return, so the stack may have moved and "
            "no record says how; a person clears this")


def hold_live_peers(backlog, task_id: str, why: str) -> list[str]:
    """Every OTHER live task waits for a person: the stack is in doubt, and one
    starting on it would act on what this task may already have changed.

    Returns the ids it held. A peer already held for a person is not among them:
    that hold is somebody else's and releasing it would undo a decision this
    call never made — which is why the release below goes by the reason this
    call wrote, not by every held card it finds.
    """
    held = []
    for row in backlog.tasks():
        if is_live(row) and row.get("status") == "todo" \
                and not row.get("blocked_by_human") and row.get("id") != task_id:
            backlog.set_status(row["id"], "held", blocked_by_human=True,
                               held_by="loop", refused_why=why)
            held.append(row["id"])
    return held


def release_live_peers(backlog, why: str) -> list[str]:
    """Free the peers a live call held, once that call's end is recorded.

    By the REASON the hold wrote, not by a list carried through the call: the
    only release used to sit in one refusal branch, so a live call that
    SUCCEEDED left every other live card held for ever — invisible, because the
    picker offers only todo, `waiting_for_human` reads only todo, and the hold
    writes no event. One successful live task killed the live lane.
    """
    freed = []
    for row in backlog.tasks():
        if row.get("status") == "held" and row.get("refused_why") == why:
            backlog.set_status(row["id"], "todo", blocked_by_human=None, refused_why=None)
            freed.append(row["id"])
    return freed


def restate_live_peers(backlog, was: str, now: str) -> list[str]:
    """Change WHY the peers are held, so the release for the old reason leaves
    them alone. A call that did not return leaves the stack in doubt, and doubt
    outlives the turn that raised it.
    """
    moved = []
    for row in backlog.tasks():
        if row.get("status") == "held" and row.get("refused_why") == was:
            backlog.set_status(row["id"], "held", refused_why=now)
            moved.append(row["id"])
    return moved
