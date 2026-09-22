"""Rewriting a refused CODE contract from the reviewer's own findings.

The planner may repair goal, files, done-when and gate within the card's
authority. A changed gate is reviewed before red-first executes it. A LIVE
task's contract stays the commander's. New reasons buy progress; the same
complaint twice or six actual rounds end replanning.
"""

from __future__ import annotations

import dataclasses

import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from backlog_status import is_live
from contract import frozen_requirement
from ending_reason import review_reason
from gate_shell import pins_a_count
from prompts import moved_under
from replan_budget import (  # noqa: F401 — public constant
    MAX_REPLANS,
    alert_stopped,
    stop_reason,
)

# the words themselves live next door; `replan.prompt_for` stays the name callers use
from replan_prompt import prompt_for
from resources import refused_before_reading

# What a rewrite keeps: identity, lineage, place in the graph, what it has spent.
KEEP = ("id", "why", "needs", "status", "sliced_from", "blocked_by_human",
        "gate_has_side_effects", "replans", "replan_history")
WANTED = ("goal", "files", "done_when", "gate")
# The gate is in here because 142 of 153 contract refusals were ABOUT the gate —
# "it can pass without the work" — and a repair step forbidden to touch the gate
# hands back the same card the reviewer just refused, for ever. Proving a gate
# red RUNS it, so a rewritten one is marked `gate_reviewed_first` and the loop
# reviews the contract before anything executes it. A LIVE gate performs the work
# itself and stays the commander's.


@dataclasses.dataclass
class Replanned:
    rewritten: bool
    why: str = ""
    task: dict | None = None


def _parse(text: str, *, strict: bool = False) -> dict | None:
    body = text.strip()
    if "```" in body:
        body = body.split("```")[1]
        body = body.split("\n", 1)[1] if body.lstrip().startswith("yaml") else body
    try:
        loaded = yaml.safe_load(body)
    except yaml.YAMLError:
        if strict:
            raise
        return None
    if not isinstance(loaded, dict):
        return None
    return {str(key).strip().lower().replace(" ", "_").replace("-", "_"): value
            for key, value in loaded.items()}


def replan_until_planned(backlog, task: dict, planner, *, space=None) -> Replanned:
    """Rewrite until a rewrite is stored or the rounds are spent: a refused
    rewrite (not a contract, outside the files, a changed gate) is itself a
    round the next planner reads, not a dead end."""
    out = Replanned(False, "no rounds left")
    while True:
        fresh = backlog.task(task["id"]) or task
        if fresh.get("status") != "refused_contract" or stop_reason(fresh):
            alert_stopped(backlog, space, fresh)
            if stop_reason(fresh):
                out = Replanned(False, f"replan stopped: {stop_reason(fresh)}")
            break
        if fresh.get("blocked_by_human"):
            break
        if space is not None:
            from triage_paths import criteria_path
            if criteria_path(backlog, space, fresh):
                return Replanned(False, "triage handled the accepted-criteria refusal")
            fresh = backlog.task(task["id"]) or fresh
        spent = int(fresh.get("replans") or 0)
        out = replan(backlog, fresh, planner)
        if out.rewritten:
            break
        after = int((backlog.task(task["id"]) or {}).get("replans") or 0)
        if after == spent:
            break   # no round spent — a harness fault, or a contract no planner may touch
                    # (a live task's). Asking again would spin: the next turn asks instead.
    return out


def _refuse(backlog, task: dict, why: str, proposed: dict | None = None) -> Replanned:
    """An answered rewrite that cannot be stored: the round is spent, and the
    next planner reads why — a refusal that costs nothing is a dead end."""
    backlog.set_status(task["id"], "refused_contract", refused_why=why, refused_rewrite=proposed,
                       # a card whose rewrites are all refused parks for the
                       # next plan phase, which re-slices it
                       requirement=task.get("requirement") or frozen_requirement(task),
                       replans=int(task.get("replans") or 0) + 1,
                       replan_history=list(task.get("replan_history") or [])
                       + [review_reason(task.get("refused_why"))])
    return Replanned(False, why)


def replan(backlog, task: dict, planner) -> Replanned:
    """Ask the planner for a better contract, check it, and write it back."""
    if is_live(task):
        return Replanned(False, "a live task's contract is the commander's: a refusal waits for a person, "
                                "never for a planner")
    if stopped := stop_reason(task):
        return Replanned(False, f"replan stopped: {stopped}; it waits for a person")
    out = planner(prompt_for(task))
    with backlog.only_writer():
        # The planner call takes minutes. A hold raised in that window, or a
        # contract edited in it, is a person's decision newer than everything
        # this rewrite was decided from: storing it would clear the hold or
        # bury the edit — and so would charging it a round. Asked FIRST, and
        # read and written as one, or the person's write lands between the
        # two. No round is spent — nobody judged the contract as it now
        # stands, and `replan_until_planned` stops on a spent-nothing answer
        # rather than asking again.
        moved = moved_under(backlog.task(task["id"]), task)
        if moved:
            return Replanned(False, moved)
        if not getattr(out, "ok", False):
            if refused_before_reading(out.kind):
                # No model read the question: another turn asks the same one.
                return Replanned(False, f"the planner did not answer ({out.kind})")
            # Paid for and no contract back — a crash, an answer cut off. The
            # counters stayed where they were, so the next turn asked and paid
            # again: `replan_refused: the planner did not answer (crash)` stood
            # in the record turn after turn (astra round 4, finding 8).
            return _refuse(backlog, task, f"the planner's call did not finish ({out.kind})")
        return _store(backlog, task, out.text)


def _store(backlog, task: dict, text: str) -> Replanned:
    """Check the planner's answer and write it back. Called under the lock."""
    try:
        fresh = _parse(text, strict=True)
    except yaml.YAMLError as error:
        return _refuse(backlog, task, f"the planner's answer was not a task contract: {error}")
    if not fresh or not all(key in fresh for key in ("goal", "files")):
        return _refuse(backlog, task, "the planner's answer was not a task contract")
    # The prompt asks for these keys and nothing else, and this is where that is
    # true: a key nobody stores is still READ on the way past (`needs: 1` reached
    # the graph check and raised), and a KEY is untrusted too — YAML's `1:` is the
    # integer 1, which no sort compares with a name (Codex, 2026-09-08).
    extra = sorted(str(key) for key in fresh if key not in WANTED)
    if extra:
        return _refuse(backlog, task, "a rewrite writes goal, files, done_when and "
                       "gate, and nothing else; this one also wrote " + ", ".join(extra))
    # A live task's gate is the commander's, and it never reaches here: `is_live`
    # already returned above, on this same, unmutated `task`.
    rewrote_gate = (str(fresh.get("gate") or "").strip()
                    and str(fresh["gate"]).strip() != str(task.get("gate") or "").strip())
    # The card's own authority, asked by the one validator every rewrite goes
    # through: the grant is a list of names, it only narrows, and a card that
    # changes code is never handed back changing none (astra round 3, finding 7 —
    # `files: []` here made an evidence card that skipped the builder, the red
    # proof and the diff review).
    from rewrite_guard import check_rewrite
    refused = check_rewrite(task, backlog.tasks(), fresh)
    if refused:
        return _refuse(backlog, task, refused, fresh)
    # Checked against the EFFECTIVE gate, whether or not it changed: a
    # rewrite that omits the gate, or restates the original unchanged,
    # leaves rewrote_gate False while a pinned original gate would still
    # reach the queue untouched -- the path that re-added the pinned
    # clause today. Refused the same way an out-of-bounds rewrite is
    # refused above -- the card keeps its old gate, and the next planner
    # reads why.
    effective_gate = str(fresh.get("gate") or task.get("gate") or "")
    pinned = pins_a_count(effective_gate)
    if pinned:
        return _refuse(backlog, task,
                       f"the gate pins EXPECTED to {pinned}: the runner's EXPECTED counts "
                       "test cases and moves as tests land — assert it only against what "
                       "the runner collects (`countTestCases()`/`run_all.EXPECTED`)")
    row = {key: task[key] for key in KEEP if key in task}
    row.update({key: fresh[key] for key in WANTED if key in fresh})
    # Frozen before this rewrite narrows anything: a card refused for its NAMES
    # is rewritten before any review (astra round 3, finding 8).
    row["requirement"] = task.get("requirement") or frozen_requirement(task)
    row["status"] = "todo"
    if rewrote_gate:
        # Proving a gate red RUNS it, so a rewritten one must be read by the
        # reviewer before anything executes it. The loop reads this and reviews
        # the contract first for exactly one round.
        row["gate_reviewed_first"] = True
    row["replans"] = int(task.get("replans") or 0) + 1
    row["replan_history"] = list(task.get("replan_history") or []) + [
        review_reason(task.get("refused_why"))]
    fields = {key: value for key, value in row.items() if key not in ("id", "status")}
    backlog.set_status(task["id"], "todo", refused_why=None, refused_rewrite=None, **fields)
    return Replanned(True, "rewritten from the reviewer's findings", backlog.task(task["id"]))
