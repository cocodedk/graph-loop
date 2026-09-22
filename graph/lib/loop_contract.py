"""The contract: the task is read before anyone edits a file.

Split out of loop_judge.py to hold the 200-line cap. loop_judge.py imports
`contract` back in, so `loop.py`'s import site does not change.
"""

from __future__ import annotations

import resources
from accepted_contract import criteria
from contract import frozen_requirement
from ending_reason import review_reason
from loop_judge_retry import moved_first
from loop_types import TaskOutcome
from prompts import contract_digest, contract_prompt
from replan_budget import alert_stopped
from worktree import Worktree


def contract(loop, task: dict, tree: Worktree, in_place: bool = False) -> TaskOutcome | None:
    """The reviewer reads the task before anyone edits a file. None means
    it was accepted; otherwise the outcome that ends the task.

    `in_place` marks a rebuild round continuing in a tree that already holds
    paid work: an outage or a refusal there must not delete it, the same way
    every other harness fault or rejection leaves it for the next round.
    """
    task_id = task["id"]
    if task.get("contract_observation") and task.get("contract_seen") == contract_digest(task):
        return None
    if not task.get("requirement"):
        # Frozen here, once: what this card was granted, in the words nobody
        # has rewritten yet. Written to the card AND to the copy this round
        # carries, because the digest reads it and every later guard compares
        # the two (`moved_under`).
        task["requirement"] = frozen_requirement(task)
        loop.backlog.note(task_id, requirement=task["requirement"])
    prompt = contract_prompt(task)
    loop.space.artifact(task_id, "contract-prompt", prompt)
    with loop.space.step(task_id, "contract") as note:
        verdict = loop.review(prompt, cwd=tree.path, space=loop.space, task_id=task_id)
        note(verdict=verdict.verdict, outcome=verdict.kind)
    loop.space.artifact(task_id, "contract-answer", verdict.raw or verdict.text)
    if not verdict.ok:
        # No verdict was written: the reviewer was limited, killed or answered
        # nothing. That is the harness talking, and it must not refuse a task.
        loop.space.event("review_unavailable", task=task_id, step="contract",
                         why=f"{verdict.kind}: {verdict.text[:200]}")
        if in_place:
            # Paid work is already in this tree: it continues there as a
            # counted round, the same way any other harness fault does —
            # never a fresh tree that re-pays the build.
            from loop_judge import back_in_place
            return back_in_place(loop, task, tree, "harness",
                                 f"the contract review did not happen ({verdict.kind})",
                                 "harness fault: the contract review did not happen; the work "
                                 "in this worktree stands — continue and say DONE",
                                 review_kind=verdict.kind)
        why = f"the contract review did not happen ({verdict.kind})"
        if not resources.refused_before_reading(verdict.kind):
            # The reviewer was paid and gave no verdict — a crash, an answer
            # that was not one. Nothing on the card moved, so the next turn
            # asked the same question and paid again, for ever (astra round 4,
            # finding 8). It costs the round the in-place path already spends
            # for this same fault; at the cap the picker stops offering the
            # card and it parks for the next plan phase, with this reason as
            # its cause. A
            # reviewer never reached costs nothing: no model read the question.
            with loop.backlog.only_writer():   # a result write like any other
                ended = moved_first(loop, task, tree, "contract", paid=False)
                if ended is not None:
                    return ended
                loop.backlog.note(task_id, refused_why=why,
                                  rebuild_round=int(task.get("rebuild_round") or 0) + 1)
        tree.remove()
        return TaskOutcome("harness", why, tree.path)
    if verdict.verdict != "ACCEPT":
        reason = review_reason(verdict.text)
        loop.space.event("refused", task=task_id, step="contract",
                         why=reason)
        # The review took minutes, and the card it was asked about can have been
        # dropped, held or rewritten in them: the same guard every other ending
        # passes, with the write in the same lock hold. Nothing is paid on a
        # first round's tree, so a moved card there leaves no tree behind.
        with loop.backlog.only_writer():
            ended = moved_first(loop, task, tree, "contract", paid=in_place)
            if ended is not None:
                return ended
            loop.backlog.set_status(task_id, "refused_contract",
                                    refused_why=reason)
            alert_stopped(loop.backlog, loop.space, loop.backlog.task(task_id))
        tree.keep(f"contract refused after paid work: {verdict.text[:200]}") if in_place else tree.remove()
        return TaskOutcome("refused", verdict.text, tree.path)
    # remember WHICH contract was accepted: a later edit must be read again.
    # The in-memory card carries it too — this round reads that copy, and a
    # rewritten gate reviewed here would otherwise be reviewed a second time.
    task["accepted_criteria"] = criteria(task)
    task["contract_seen"] = contract_digest(task)
    loop.backlog.note(task_id, contract_seen=task["contract_seen"],
                      accepted_criteria=task["accepted_criteria"])
    return None
