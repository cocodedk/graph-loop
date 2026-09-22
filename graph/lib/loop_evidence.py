"""When the gate runs before the build, or not at all.

Split out of loop.py to hold the 200-line cap. `red_first` decides whether
proving the gate red is worth doing at all -- a live gate performs the work
it measures, a rebuild round already proved it red before round one, and a
no-files evidence card's gate runs once, in `judge`, after the contract, so
proving it red first would just run it for no reason.
"""

from __future__ import annotations

from backlog_reach import overlap
from backlog_status import is_live, settled
from gate_reports import excerpt
from gates import GREEN_ALREADY, prove_red
from loop_contract import contract
from loop_environment import environment_ending
from loop_judge_retry import gate_left_its_lane, moved_first
from loop_types import TaskOutcome
from worktree import Worktree


def red_first(loop, task: dict, tree: Worktree, gate: str, rebuild: int,
              in_place: bool, reviewed_first: bool) -> TaskOutcome | None:
    """Prove the gate fails before anything is built against it. A gate the
    planner rewrote is read by the reviewer BEFORE anything runs it: proving
    red executes the gate, and planner-written shell has been reviewed by
    nobody until the contract review sees it. A rebuild round does NOT
    excuse that -- `in_place and not reviewed_first` would let a rewritten
    gate reach `bash -c` unread, which is the one thing this mark exists to
    stop. None means proved (or excused); otherwise the outcome that ends
    the task."""
    task_id = task["id"]
    if reviewed_first:
        refused = contract(loop, task, tree, in_place)
        if refused is not None:
            return refused
        loop.backlog.note(task_id, gate_reviewed_first=None)
    evidence = not is_live(task) and not task.get("files")
    ending = None
    if is_live(task) or (in_place and not reviewed_first) or evidence:
        why = ("the gate performs the work it measures" if is_live(task)
               else "the gate only observes, once, after the contract" if evidence
               else f"rebuild round {rebuild}: the gate was proved red before round one")
        loop.space.event("skipped_red_first", task=task_id, why=why)
        proved, why = True, f"red-first skipped: {why}"
    else:
        with loop.space.step(task_id, "red_first") as note:
            proved, why = prove_red(gate, tree.path, task.get("expect_red") or "")
            note(proved=proved)
        stopped = environment_ending(loop, task, tree, why, gate, "red_first")
        if stopped is not None:
            loop.space.artifact(task_id, "red-first", why)
            return stopped
        # Whatever colour the gate came back, before either branch below acts
        # on it: this run just executed reviewed shell, same as a builder's
        # edits, and a HEAD move or a stray file here must not ride along into
        # build(), whose own on_base check would then blame the BUILDER for it.
        # The ending -- if any -- returns below, AFTER the artifact write: a
        # scope fault is still evidence of what the gate said before it wandered.
        ending = gate_left_its_lane(loop, task, tree)
    loop.space.artifact(task_id, "red-first", why)
    if ending is not None:
        return ending
    if not proved:
        if in_place and why == GREEN_ALREADY:
            # The tree carries a previous round's work, not a fresh one: a
            # green gate here is that work standing, not a fault to park.
            # No production writer ever clears a queued finding -- every
            # rebuild write only appends one (loop_judge.py, worktree_refs.py,
            # loop_judge_retry.py) -- so there is no "resolved" state to
            # detect here. The builder always gets this round, findings and
            # all (empty or not), and judge() reads the diff it produces.
            loop.space.event("gate_green_in_place", task=task_id, why=why)
            return None
        # A task the loop cannot start is marked, or the picker hands it back
        # on the next turn and the same refusal is paid for again — but only
        # while it is still the task this round started from: the gate is a long
        # call, and a card decided while it ran is not written over.
        with loop.backlog.only_writer():
            ended = moved_first(loop, task, tree, "red_first", paid=in_place)
            if ended is not None:
                return ended
            rows = loop.backlog.tasks()
            closed = settled(rows)
            peers = [row for row in rows if row.get("id") != task_id
                     and overlap(set(task.get("files") or []), set(row.get("files") or []))]
            delivered = ", ".join(row["id"] for row in peers if row.get("status") == "done")
            if why == GREEN_ALREADY and delivered and all(row["id"] in closed for row in peers):
                why = ("work was already delivered; gate passed before any work"
                       f"; done cards listing these files: {delivered}")
                loop.backlog.set_status(task_id, "done", done_why=why, refused_why=None)
                loop.space.event("done", task=task_id, why=why)
                tree.remove()
                return TaskOutcome("done", why)
            loop.backlog.set_status(
                task_id, "green_already" if why == GREEN_ALREADY else "unprovable",
                refused_why=excerpt(why, tail=False))
        loop.space.event("refused", task=task_id, step="red_first", why=excerpt(why, tail=False))
        tree.keep(f"gate not proved red: {why[:200]}")
        return TaskOutcome("refused", why, tree.path)
    return None
