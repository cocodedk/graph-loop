"""The two stalls that have a prepared choice instead of a fixed replan route."""

from __future__ import annotations

import re

import distress
from accepted_contract import accepted_criteria, changed_criteria, criteria
from backlog_decision import can_replan
from backlog_status import spent_its_rounds
from contract import contract_digest, frozen_requirement, moved_under
from ending_reason import review_reason
from loop_resume import finished
from triage_evidence import _read
from triage_path_jev import choose
from worktree import KEEP_NOTE, Worktree, _git


def eligible(task: dict) -> bool:
    return can_replan(task) and not spent_its_rounds(task)


def contract_path(book, space, task: dict) -> bool:
    """True when the path handled this card; False leaves it to the replanner."""
    if not eligible(task) or task.get("triage") != "contract":
        return False
    rows = [row for row in space.events() if row.get("task") == task["id"]]
    refused = next((row for row in reversed(rows) if row.get("kind") == "refused"), {})
    if refused.get("step") != "contract":
        return False
    judges = [row for row in book.tasks() if row["id"] in (task.get("needs") or [])
              and row.get("status") == "done" and row.get("gate_until_kept")]
    said = str(task.get("refused_why") or refused.get("why") or "")
    names = [str(name) for row in judges for name in [row["id"], *(row.get("files") or [])]]
    if not judges or not (re.search(r"\b(judge|bypass|case)\b", said, re.IGNORECASE)
                          or any(name.lower() in said.lower() for name in names)):
        return False
    evidence = {"refusal": said, "card": task["id"], "stage": task.get("stage"),
                "files": task.get("files"), "replans": int(task.get("replans") or 0),
                "judges": [{key: row.get(key) for key in
                            ("id", "stage", "files", "status", "gate_until_kept")}
                           for row in judges]}
    decision = choose(space, task, "judge_gap", evidence)
    with book.only_writer():
        fresh = book.task(task["id"])
        if moved_under(fresh, task) or not eligible(fresh):
            return True
        if decision["path"] == "rewrite":
            return False
        if decision["path"] == "probe_in_gate":
            return False  # replan_prompt already carries the executed-probe instruction
        if decision["path"] == "slice":
            book.set_status(task["id"], "needs_slice")
        elif decision["path"] == "accept_with_observation":
            fresh["requirement"] = fresh.get("requirement") or frozen_requirement(fresh)
            book.set_status(task["id"], "todo", refused_why=None,
                            requirement=fresh["requirement"], accepted_criteria=criteria(fresh),
                            contract_seen=contract_digest(fresh), contract_observation=said)
        else:
            hold(book, task, decision, space)
    return True


def criteria_path(book, space, task: dict) -> bool:
    """Handle only an accepted-criteria refusal following an actual diff rejection."""
    if not eligible(task) or not str(task.get("refused_why") or "").startswith(
            "this task's accepted criteria are fixed:"):
        return False
    proposed = task.get("refused_rewrite")
    if proposed is None:
        from replan import _parse
        artifact = next((row for row in reversed(space.events())
                         if row.get("task") == task["id"]
                         and row.get("name") == "replan-answer"), {})
        proposed = _parse(_read(artifact.get("path"), space.root) or "")
    if proposed is None or not changed_criteria(task, proposed):
        return False
    refusal = task.get("diff_review_refusal") or prior_diff_refusal(space, task)
    if not refusal:
        return False
    evidence = {"findings": refusal["findings"], "card": task["id"],
                "accepted_criteria_digest": task.get("contract_seen"),
                "accepted_criteria": accepted_criteria(task),
                "changed_criteria_would_refuse": bool(changed_criteria(task, proposed)),
                "rewrite_refusal": task["refused_why"], "replans": task.get("replans")}
    decision = choose(space, task, "fixed_criteria", evidence)
    with book.only_writer():
        fresh = book.task(task["id"])
        if moved_under(fresh, task) or not eligible(fresh):
            return True
        path = decision["path"]
        if path == "reopen_contract":
            # This choice answers the guard refusal. Restoring the original
            # finding is not a second reviewer making the same complaint.
            book.note(task["id"], accepted_criteria=None, contract_seen=None,
                      contract_observation=None, accepted_diff=None, finished=None,
                      replan_history=list(fresh.get("replan_history") or [])
                      + [review_reason(fresh.get("refused_why"))],
                      refused_why=refusal["findings"], refused_rewrite=None, gate_reviewed_first=True)
            return False  # the remaining bounded replan must face contract review again
        receipt = refusal.get("finished") or {}
        if path == "accept_change" and receipt.get("contract") == contract_digest(fresh) \
                and receipt.get("tree") == fresh.get("rebuild_from"):
            book.set_status(task["id"], "todo", refused_why=None, refused_rewrite=None,
                            finished=receipt, accepted_diff=receipt,
                            review_observation=refusal["findings"])
        else:
            hold(book, task, decision, space)
    return True


def prior_diff_refusal(space, task: dict) -> dict:
    """Older cards have findings and artifacts, before the explicit review receipt."""
    if not task.get("rejections"):
        return {}
    rows = [row for row in space.events() if row.get("task") == task["id"]]
    review = next((row for row in reversed(rows) if row.get("step") == "diff_review"), {})
    if review.get("outcome") != "ok" or review.get("verdict") != "REJECT":
        return {}
    refusal = {"findings": task["rejections"][-1], "finished": {}}
    artifact = next((row for row in reversed(rows) if row.get("name") == "diff"), {})
    diff = _read(artifact.get("path"), space.root)
    path = task.get("rebuild_from")
    if diff is not None and path:
        try:
            tree = Worktree(path, task["id"], _git(path, "rev-parse", "HEAD").strip())
            tree.path = path
            if tree.diff(paths=[f":(exclude){KEEP_NOTE}"]) == diff \
                    and task.get("contract_seen") == contract_digest(task):
                refusal["finished"] = finished(task, tree, "gate", diff)
        except (OSError, RuntimeError):
            pass  # no matching paid work: accept_change must hold instead
    return refusal


def hold(book, task: dict, decision: dict, space=None) -> None:
    """The person sees exactly the question and evidence the model saw."""
    distress.park(book, space, task["id"], decision["why"])
    book.note(task["id"], blocked_by_human=True, held_by="needs_person",
              path_question=decision["question"], path_reason=decision["why"])
