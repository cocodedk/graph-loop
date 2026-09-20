"""What one planner answer means: validate it, have it reviewed, publish it.

Split from `slicer` at the 200-line cap; `slicer` stays the one door and
re-exports `run_answer`.
"""

from __future__ import annotations

import copy
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
GRAPH_LIB = HERE.parent / "graph" / "lib"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GRAPH_LIB))

import asking
from backlog import Backlog  # type: ignore[import-not-found]
from contracts import mapping, validate
from intelligence import review
from prompts import moved_under  # type: ignore[import-not-found]
from slicer_state import close, trace
from tree import CardMoved, publish


def run_answer(text: str, *, repo: pathlib.Path, backlog: pathlib.Path,
               sources: list[pathlib.Path], target_id: str = "",
               started: dict | None = None, reviewer=None, checker=None) -> tuple[str, str]:
    # every review reads the checkout the planner read (`ask(question, repo)`)
    judge = reviewer or (lambda question: review(question, repo))
    book = Backlog(backlog)
    rows = book.tasks()
    target = book.task(target_id) if target_id else None
    if target_id and not target:
        raise KeyError(f"no task {target_id} in {backlog}")
    if started is not None:
        # Before `validate`, not after: a hold raised while the planner ran
        # makes `assert_wall` refuse, and main answers a refusal with a repair
        # round — two more paid planner calls for a decision nobody disputes.
        # A plain requeue still reaches `assert_wall` (a status change is not a
        # contract edit), and `_not_a_wall` skips that one uncharged as before.
        moved = moved_under(target, started)
        if moved:
            raise CardMoved(moved)
    answer = validate(mapping(text), repo=repo, sources=sources, rows=rows, target=target)
    trace(backlog, "validated", result=answer["result"],
          atoms=len((answer.get("molecule") or {}).get("atoms") or []))
    if answer["result"] == "NEEDS_PERSON":
        return "needs_person", answer["reason"]
    if answer["result"] == "NO_GAP":
        try:
            coverage_question = asking.coverage_prompt(repo, sources, rows)
            trace(backlog, "coverage_review_call")
        except ValueError as error:
            return "planning_refused", str(error)
        verdict = judge(coverage_question)
        trace(backlog, "coverage_review_answered", ok=bool(verdict.ok))
        if not verdict.ok:
            return ("review_unavailable" if verdict.down else "coverage_refused"), verdict.why
        close(backlog, sources, verdict.text, repo, rows)
        return "covered", answer["reason"]
    if checker is not None:
        answer = _checked(answer, checker, backlog, dict(repo=repo, sources=sources,
                                                         rows=rows, target=target))
    if target:
        trace(backlog, "progress_review_call", target=target_id)
        verdict = judge(asking.progress_prompt(repo, target, answer["molecule"]))
        trace(backlog, "progress_review_answered", ok=bool(verdict.ok))
        if not verdict.ok:
            return ("review_unavailable" if verdict.down else "progress_refused"), verdict.why
    name = publish(backlog, answer["molecule"], target_id, started)
    trace(backlog, "published", molecule=str(name), sliced_from=target_id or "(source gap)")
    return "published", name


def _checked(answer: dict, checker, backlog: pathlib.Path, args: dict) -> dict:
    """Findings refuse the answer; a changed molecule is validated again like a planner's."""
    try:
        # a copy: a checker that edits in place and then fails, or returns the
        # molecule it edited, must not alter or hide a change from the original
        checked = checker(copy.deepcopy(answer["molecule"]))
    except Exception:
        return answer  # a checker that fails is not a reason to refuse the plan
    changed = checked.molecule != answer["molecule"]
    trace(backlog, "cut_checked", findings=len(checked.findings), changed=changed)
    if checked.findings:
        raise ValueError("; ".join(str(finding) for finding in checked.findings))
    if changed:
        return validate({**answer, "molecule": checked.molecule}, **args)
    return answer
