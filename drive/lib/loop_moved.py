"""Whether the card is still the one this round started from, and what a scope
fault writes when it is.

Split from `loop_judge_retry` at the 200-line cap. `loop_judge_retry` imports
both names back, so `loop_contract.py` and `loop_steps.py` keep reaching them
there and `loop_judge` keeps re-exporting them.
"""

from __future__ import annotations

from loop_types import TaskOutcome
from prompts import moved_under


def moved_first(loop, task: dict, tree, step: str, paid: bool = True) -> TaskOutcome | None:
    """The one guard every ending passes before it writes the card.

    A person can hold a card or edit its contract WHILE the round runs, and
    every write below decides from the older card: a requeue clears the hold
    (`Backlog._apply`), and a round is charged for a finding about a contract
    that no longer stands. None means the card is still the one this round
    started from; otherwise the tree is kept, the reason is recorded, and
    nothing is overwritten.

    `paid` is false where nothing has been bought in this tree yet — a first
    round's contract review or red proof, which run before any builder. A
    recorded path is not a paid tree: pointing the card at one would let the
    next round skip red-first on a tree nobody proved, so it goes instead,
    exactly as those steps' own refusals remove it.
    """
    with loop.backlog.only_writer():
        current = loop.backlog.task(task["id"])
        moved = moved_under(current, task)
        if not moved:
            return None
        loop.space.event("card_moved", task=task["id"], step=step, why=moved,
                         worktree=tree.path)   # recorded while there is still a path to name
        tree.keep(moved) if paid else tree.remove()
        if current is not None and paid:
            # the loop's own pointer at its paid tree, not a person's decision:
            # without it the next round cuts a fresh tree and re-pays the build.
            loop.backlog.note(task["id"], rebuild_from=tree.path)
        return TaskOutcome("held", moved, tree.path)


def scope_fault(loop, task: dict, why: str, **fields) -> str:
    """What the gate or the BUILDER did, recorded — and written on the card only
    while the card is still the one this round started from. Answers why it is
    not, "" when it still is, so the caller ends the round `held` rather than
    `failed`.

    Either is a long call: a drop, a hold or a rewrite can land while it runs,
    and `out_of_scope` written over it would bury that decision — and
    `out_of_scope` is a wall the slicer then takes, so the dropped card comes
    back (astra round 4, finding 2). The fault itself is recorded either way;
    the card is not rewritten. One guard for both callers, never one per caller.
    """
    task_id = task["id"]
    loop.space.event("failed", task=task_id, step="scope", why=why)
    with loop.backlog.only_writer():          # guard and write in one hold
        moved = moved_under(loop.backlog.task(task_id), task)
        if moved:
            loop.space.event("card_moved", task=task_id, step="scope", why=moved)
        else:
            loop.backlog.set_status(task_id, "out_of_scope", refused_why=why, **fields)
        return moved
