"""The judge: the gate, the diff review, the rebuild rounds and the keep.

A rejected diff is a finding list, not a verdict on the task: the builder gets
it back in the same worktree, REBUILD_ROUNDS rounds in all, before a person is
needed. Three: the first campaign's salvages all landed by round three.
"""

from __future__ import annotations

import datetime

from backlog_status import REBUILD_ROUNDS, is_live  # noqa: F401 — loop.py names it here
from gates import run_gate
from keep import CombinedGateFailed
from loop_contract import contract  # noqa: F401 — loop.py imports it from here
from loop_diff_review import review_change
from loop_environment import environment_ending
from loop_judge_gates import (
    _gate_is_defective,
    _gate_owner,
    _gates_on_the_branch,
    _send_to_its_owner,
)
from loop_judge_retry import (
    _send_back,
    back_in_place,
    gate_left_its_lane,
    moved_first,
)
from loop_resume import finished
from loop_types import TaskOutcome
from prompts import revision
from worktree import Worktree, added_beside


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def judge(loop, task: dict, tree: Worktree, gate: str, rebuild: int) -> TaskOutcome:
    task_id = task["id"]
    with loop.space.step(task_id, "gate") as note:
        # A live gate performs the work it measures: it needs Docker and the
        # database, and its text is the commander's, never a planner's.
        result = run_gate(gate, tree.path, confine=not is_live(task))
        note(passed=result.passed, code=result.code)
    loop.space.artifact(task_id, "gate-output", result.output)
    if not result.passed:
        ending = environment_ending(loop, task, tree, result.output, gate, "gate")
        if ending is not None:
            return ending
    if not is_live(task):
        # Never for a live gate: it performs the work it measures, and it
        # runs alone. `gate_left_its_lane` is this run's own check, whether
        # this is a no-files card's only run, an ordinary card's, or
        # (in-place, a green gate standing in for a build) judge's own rerun
        # of it -- red_first's own run of the same gate is checked there.
        ending = gate_left_its_lane(loop, task, tree)
        if ending is not None:
            return ending
    evidence = not is_live(task) and not task.get("files")
    if not result.passed:
        why = result.why
        loop.space.attempt(task_id, account="gate", kind="ok", failed_gate=True)
        # The watchdog reads endings, not attempts: without this event a task
        # that fails its gate the same way for ever is invisible to it. It is
        # also `needs_slice`'s own record of the reason, task by task.
        loop.space.event("failed", task=task_id, step="gate", why=why)
        # One failure is worth a second try, in the SAME worktree; two of
        # them failing THE SAME WAY mean the task is wrong rather than the
        # builder, so it waits to be re-sliced instead.
        if loop.space.needs_slice(task_id):
            with loop.backlog.only_writer():   # guard and write together
                ended = moved_first(loop, task, tree, "needs_slice")
                if ended is not None:
                    return ended
                tree.keep(f"gate failed: {why}")
                loop.backlog.set_status(task_id, "needs_slice", refused_why=why)
        else:
            _send_back(loop, task, tree, rebuild, why, note="gate failed", gate=True)
        return TaskOutcome("failed", why, tree.path)

    if evidence:
        # No files: nothing to build or review — the green gate above is it, and
        # past the same guard as every other ending, in one lock hold: the gate
        # is a long call too, and a decision made while it ran is the newer one.
        with loop.backlog.only_writer():
            ended = moved_first(loop, task, tree, "keep")
            if ended is not None:
                return ended
            loop.backlog.set_status(task_id, "done", commit=None, worktree=tree.path, kept_at=_now())
        loop.space.event("accepted", task=task_id, worktree=tree.path, commit=None)
        return TaskOutcome("done", "gate green, no files to build or keep", tree.path)

    ending = review_change(loop, task, tree, rebuild)
    if ending is not None:
        return ending

    commit = None
    with loop.backlog.only_writer():
        # The same guard every other ending passes, and here it holds the lock
        # across the keep as well: a hold or a contract edit landing between
        # the check and the publish would be marked done over.
        ended = moved_first(loop, task, tree, "keep")
        if ended is not None:
            return ended
        commit = _keep(loop, task, tree, rebuild)
        if isinstance(commit, TaskOutcome):
            return commit
        if not commit:
            # Nothing to commit (the work is already on the branch): the keeper's
            # record never ran, so the card is written done here.
            loop.backlog.set_status(task_id, "done", commit=commit,
                                    worktree=tree.path, kept_at=_now())
    if commit and loop.keeper:
        # The card is already done; a push that fails only alerts — losing the
        # task over an unreachable remote would throw away real, kept work.
        with loop.space.step(task_id, "push") as note:
            failed = loop.keeper.push()
            note(pushed=not failed)
        if failed:
            loop.space.alert(task_id, f"kept as {commit[:8]} but not pushed: {failed}")
    loop.space.event("accepted", task=task_id, worktree=tree.path, commit=commit)
    return TaskOutcome("done", f"gate green, review accepted, kept as {commit}",
                       tree.path)


def _keep(loop, task: dict, tree, rebuild: int):
    """Put the accepted work on the branch. The commit id, None when there was
    nothing to commit, or the outcome that ends the task. Called under the
    backlog lock, which the keeper's own `publishing` re-enters."""
    task_id = task["id"]
    commit = None
    if loop.keeper:
        # The card as `moved_first` just proved it, in that same lock hold: a
        # keep whose card-write is lost leaves only the branch and this name,
        # and the turn that reconciles it reads both (`publishing.reconcile`).
        loop.backlog.note(task_id, keep_revision=revision(task))
        with loop.space.step(task_id, "keep") as note:
            files = list(task.get("files") or [])
            if files and task.get("may_add_files"):
                files += added_beside(tree.path, files)   # the split's new file is part of the work
            try:
                # Only a CODE card's gate is re-run on the combined tree: a live
                # gate acts on the stack, and running it twice would repeat a
                # one-shot reset, run or kill. A live card runs alone anyway, so
                # no sibling can have moved the branch under it.
                # This card's gate AND the gates of the cards already kept: a lane
                # can pass alone and break work that landed before it, and the
                # branch is what a person reads. Live gates are never re-run.
                commit = loop.keeper.keep(
                    task_id, tree.path, task.get("goal", ""), files=files or None,
                    gates=lambda: _gates_on_the_branch(loop, task),
                    record=lambda sha: loop.backlog.set_status(
                        task_id, "done", commit=sha, worktree=tree.path, kept_at=_now()),
                    publishing=loop.backlog.only_writer)
            except CombinedGateFailed as clash:
                note(commit=None, clash=str(clash))
                output = clash.failure.result.output if clash.failure else str(clash)
                ending = environment_ending(loop, task, tree, output, clash.gate, "combined_gate")
                if ending is not None:
                    return ending
                owner = _gate_owner(loop, task, clash.gate)
                defective = _gate_is_defective(loop, task, clash) if owner else False
                if defective is None:
                    return back_in_place(
                        loop, task, tree, "harness", "the baseline gate could not be checked",
                        "Baseline evidence is unavailable; the finished work needs a gate check, "
                        "not builder changes.", finished=finished(task, tree, "gate", tree.diff()))
                if defective:
                    # ANOTHER card's gate, red on the branch tip WITHOUT this
                    # card's work — or one that edited the tree it judged: the
                    # owner gets the repair and this card waits for it
                    # (`loop_judge_gates`). A gate that was GREEN on the tip and
                    # goes red beside this diff is a regression this card
                    # caused, and falls through below.
                    return _send_to_its_owner(loop, task, tree, owner, clash)
                # This card's own gate, or a sibling's that this work turned
                # red: back for a rebuild round with the finding, in its own
                # worktree.
                return _send_back(loop, task, tree, rebuild, str(clash))
            note(commit=commit)
    return commit
