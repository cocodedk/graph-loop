"""Whether a card has already finished, before a turn opens anything for it.

Split out of `loop.py` at the 200-line cap. A campaign resumes at unfinished
branch frontiers, but a stale reference — an old lane's plan, a resumed
session naming a card the branch already kept — can still hand `run_task` a
card that is `done`. Nothing about that card needs a worktree, a builder, a
reviewer or a backlog write: the work is already accepted, and touching the
card again would only risk moving what was already kept.
"""

from __future__ import annotations

from loop_types import TaskOutcome


def already_finished(task: dict) -> TaskOutcome | None:
    """`None` when there is a turn to run; the finished result, unchanged and
    without a backlog write, when the card is `done` already."""
    if task.get("status") != "done":
        return None
    return TaskOutcome("done", "already finished, not reopened", task.get("worktree") or "")
