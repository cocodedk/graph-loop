"""Where a round that did not end in a keep goes: back to the builder with the
finding, or on in the same worktree after a harness fault; and a gate that
moves HEAD or writes outside its lane ends the round on the spot.

Split out of `loop_judge` at the 200-line cap; `loop_judge` imports the names
back, so `loop_contract.py` and `loop_steps.py` keep reaching them there.
"""

from __future__ import annotations

import resources
from backlog_status import REBUILD_ROUNDS
from loop_moved import moved_first, scope_fault  # the door stays here
from loop_types import TaskOutcome
from worktree import HeadMoved, changed_outside, save_and_go


def gate_left_its_lane(loop, task: dict, tree) -> TaskOutcome | None:
    """Run right after every gate execution on a non-live card (never for a
    live gate, which performs the work it measures and runs alone). The gate
    just ran reviewed shell, same as a builder's edits: it can move HEAD or
    write outside the task's files, on ANY of its runs -- red_first's first
    look at it, judge's own re-run, or a no-files card's only run.

    A HeadMoved fault here is the GATE's doing, not the builder's: `discard`
    blames the builder's own edits and charges a rebuild round, which is
    wrong for a tree the builder may never have touched this round. None
    means the tree is still on base and in scope; otherwise the ending — `held`
    where the card was decided while the gate ran, because `failed` is a state
    later writers act on and the lane's own re-slice (`lanes.run_lanes`) would
    write `needs_slice` straight over the decision this preserved."""
    try:
        tree.on_base()
    except HeadMoved:
        why = "the gate moved HEAD off the base"
        # Its HEAD is not the base plus edits, so nothing here can be REUSED --
        # but a builder was paid in this tree before the gate ran, so what it
        # holds is written down against the recorded base and the card pointed
        # at it before the tree goes (`save_and_go`, the same door `discard`
        # uses; the tree stays when that save fails).
        save_and_go(loop, task["id"], tree)
        moved = scope_fault(loop, task, why, rebuild_from=None)
        return TaskOutcome("held" if moved else "failed", moved or why, tree.path)
    outside = changed_outside(tree.path, task.get("files") or [],
                              bool(task.get("may_add_files")))
    if outside:
        why = f"the gate wrote outside its files: {', '.join(outside)}"
        moved = scope_fault(loop, task, why)
        tree.keep(why)
        return TaskOutcome("held" if moved else "failed", moved or why, tree.path)
    return None


def back_in_place(loop, task: dict, tree, state: str, said: str, note: str,
                  *, review_kind: str = "", build_kind: str = "",
                  finished: dict | None = None) -> TaskOutcome:
    """A harness fault after paid work — a timeout, a crash, a review that did
    not happen: the card continues in the SAME kept tree as a counted round,
    never a fresh tree that re-pays the build, and at the cap a person looks.

    `review_kind` and `build_kind` carry the provider's outcome. Capacity,
    limits and auth failures spend no round, even after paid builder work:
    the card goes back to todo in the same worktree. Other faults, including
    crashes and malformed answers, still spend a bounded round.

    `finished` is the phase this round DID finish (`loop_resume`), passed only
    by a site that ran it: the next attempt re-runs what is missing and no
    more. None clears any older record, so a stale tick never survives a round.
    """
    # ONE lock hold, guard and write together: `moved_first` reading the
    # card and this write are two halves of one decision, and another
    # writer landing between them is read too early and overwritten a
    # moment later. `moved_first` re-enters the lock, which is free.
    with loop.backlog.only_writer():
        ended = moved_first(loop, task, tree, "rebuild")
        if ended is not None:
            return ended
        task_id = task["id"]
        tree.keep(f"{said}; the work is here")
        if resources.refused_before_reading(review_kind or build_kind):
            loop.space.event("rebuild_queued", task=task_id,
                             round=int(task.get("rebuild_round") or 0), charged=False,
                             why=f"{said}; the provider was unavailable, no round spent")
            loop.backlog.set_status(task_id, "todo", rebuild_from=tree.path,
                                    rejections=list(task.get("rejections") or []) + [note],
                                    refused_why=None, finished=finished)
            return TaskOutcome(state, f"{said}; queued to continue in its worktree, not charged",
                               tree.path)
        rounds = int(task.get("rebuild_round") or 0) + 1
        if rounds < REBUILD_ROUNDS:
            loop.space.event("rebuild_queued", task=task_id, round=rounds, charged=True,
                             why=f"{said}; continue in place")
            loop.backlog.set_status(task_id, "todo", rebuild_round=rounds, rebuild_from=tree.path,
                                    rejections=list(task.get("rejections") or []) + [note],
                                    refused_why=None, finished=finished)
            return TaskOutcome(state, f"{said}; queued to continue in its worktree", tree.path)
        why = f"{said} {rounds} rounds running; a person re-slices"
        loop.space.event("rejected", task=task_id, why=why)
        loop.backlog.set_status(task_id, "rejected", rebuild_round=rounds, refused_why=why)
        return TaskOutcome("rejected", why, tree.path)


def _send_back(loop, task: dict, tree, rebuild: int, why: str,
               note: str = "review rejected", *, gate: bool = False) -> TaskOutcome:
    """A rejected diff, work that is red beside what landed first, or a gate
    that failed without yet spinning: back to the builder in its own
    worktree with the finding, to the round cap.

    `gate` marks the one caller whose round the CARD'S OWN gate cost — passed
    only by `judge`'s gate-failure branch, so `gate_rounds` counts charges and
    not failures. A gate that fails the same way twice ends the card as
    `needs_slice` and never reaches here, and a combined-gate clash is a
    regression this card caused, so neither is the gate's to give back
    (`triage_repairs`). The first charge also clears any refund watermark the
    card was carrying from before the counter existed."""
    with loop.backlog.only_writer():   # guard and write together; see back_in_place
        ended = moved_first(loop, task, tree, "rebuild")
        if ended is not None:
            return ended
        task_id = task["id"]
        rounds = rebuild + 1
        charged = int(task.get("gate_rounds") or 0) + (1 if gate else 0)
        # The two counters are a pair and start together. A card refunded while
        # the refund still counted journal failures carries the watermark and no
        # counter: it describes charges this one never saw, and left standing it
        # is subtracted from every charge the card earns from here.
        counters: dict = {"gate_rounds": charged or None}
        if gate and "gate_rounds" not in task:
            counters["gate_rounds_refunded"] = None
        # every finding, whole: a builder cannot fix what was cut off
        findings = list(task.get("rejections") or []) + [why]
        tree.keep(f"{note}: {why[:200]}")
        if rounds < REBUILD_ROUNDS:
            # Back to the builder with the findings, same worktree, no new
            # contract review: the picker offers it again as todo.
            loop.space.event("rebuild_queued", task=task_id, round=rounds,
                             why=why[:2000])
            loop.backlog.set_status(task_id, "todo", rebuild_round=rounds,
                                    rebuild_from=tree.path, rejections=findings,
                                    refused_why=None, **counters)
        else:
            loop.space.event("rejected", task=task_id, why=why[:2000])
            loop.backlog.set_status(task_id, "rejected", rebuild_round=rounds,
                                    rejections=findings, refused_why=why[:2000],
                                    **counters)
        return TaskOutcome("rejected", why, tree.path)
