"""New complaints are progress; repeated complaints and six rounds stop."""

from __future__ import annotations

from difflib import SequenceMatcher

from ending_reason import review_reason

MAX_REPLANS = 2
MAX_ROUNDS = 6
SIMILARITY = 0.9


def same_complaint(previous: str, current: str) -> bool:
    before, after = (" ".join(review_reason(text).lower().split())
                     for text in (previous, current))
    return bool(before and after and (before == after or
                SequenceMatcher(None, before, after, autojunk=False).ratio() >= SIMILARITY))


def stop_reason(task: dict) -> str:
    """`replans` counts actual calls; only consecutive reasons spend the budget."""
    if int(task.get("replans") or 0) >= MAX_ROUNDS:
        return "the ceiling"
    history = list(task.get("replan_history") or [])
    if history and same_complaint(history[-1], str(task.get("refused_why") or "")):
        return "the same complaint twice"
    return ""


def alert_stopped(backlog, space, task: dict) -> None:
    from backlog_status import is_live
    from slice_outcome import MAX_SLICES

    if task.get("status") != "refused_contract" or not stop_reason(task):
        return
    with backlog.only_writer():
        task = backlog.task(task["id"])
        shape = stop_reason(task) if task and task.get("status") == "refused_contract" else ""
        if not shape:
            return
        if not is_live(task) and not task.get("blocked_by_human"):
            if int(task.get("slices") or 0) < MAX_SLICES:
                backlog.set_status(task["id"], "needs_slice")
                return
            backlog.note(task["id"], blocked_by_human=True, held_by="loop")
        if space is None:
            return
        why = f"replan stopped: {shape}; a person must look at this card"
        if not any(row.get("kind") == "alert" and row.get("task") == task["id"]
                   and row.get("why") == why for row in space.events()):
            space.alert(task["id"], why)
