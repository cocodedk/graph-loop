"""Work that was done and then thrown away, split from `doctor.py` at the
200-line cap. This is the worst thing the loop can do while nobody is
watching: pay a builder for an answer and never keep it.
"""

from __future__ import annotations

import pathlib

from doctor_types import Complaint


def check_costly_silence(space, explained: set | None = None, rows: list[dict] | None = None,
                         claimed: dict | None = None) -> list[Complaint]:
    """Work that was done and then thrown away, which is the worst thing here.

    `explained` names the tasks a person has answered for: a task sliced in the
    backlog (its successor carries the findings and its worktree as prior art),
    or one a "dropped" event names WITH a why — the complaint asks for that
    why, so a drop without one is still a complaint.
    """
    rows = space.events() if rows is None else rows
    kept = {row.get("task") for row in rows if row.get("kind") == "accepted"}
    kept |= explained or set()
    # A drop answers for the attempts before it, never for work paid later.
    dropped_at = {row.get("task"): index for index, row in enumerate(rows)
                  if row.get("kind") == "dropped" and str(row.get("why") or "").strip()}
    # A task still claimed is still moving — its gate or review runs between the
    # build and the keep, and the first version of this check cried salvage over
    # a gate that was three minutes into the broker suite.
    still_moving = set(space.claimed_now() if claimed is None else claimed)
    # A rejected diff queued for its next round is still moving too: its work
    # waits in the worktree for the builder, not for a person.
    # ... until any later ending strands it again: an accepted keep, a capped
    # rejection, a scope or gate failure, a builder that stopped, a refusal.
    ENDINGS = ("accepted", "rejected", "failed", "needs_a_person", "refused",
               "review_unavailable")
    last: dict = {}
    for row in rows:
        if row.get("kind") in ENDINGS + ("rebuild_queued",):
            last[row.get("task")] = row.get("kind")
    still_moving |= {task for task, kind in last.items() if kind == "rebuild_queued"}
    # One line per TASK, not per round: four rounds of the same task filled the
    # board with the same complaint and buried the rest.
    spent: dict = {}
    for index, row in enumerate(rows):
        if row.get("kind") != "attempt" or not row.get("counted"):
            continue
        if row.get("account") == "plan" or row.get("task") == "the slicer":
            continue   # plan-account calls (planning and triage), plus the
            # slicer, build nothing to keep; each result is recorded separately
        if row.get("purpose") in ("review", "decide"):
            continue   # a review answers about a build and a decision about a
            # card; neither produces work to keep, and what deciding cost is
            # reported on its own line (`view_decisions.spend`)
        task = row.get("task")
        if task in kept or task in still_moving or index < dropped_at.get(task, -1):
            continue
        cost = row.get("cost") or 0
        if cost and cost > 1.0:
            spent[task] = spent.get(task, [0, 0.0])
            spent[task][0] += 1
            spent[task][1] += cost
    # A rebuild round continues in the SAME worktree: its earlier rounds' work is
    # still there, not lost. Only a task whose worktree is gone lost anything.
    alive = {row.get("task") for row in rows if row.get("kind") == "worktree"
             and row.get("path") and pathlib.Path(str(row["path"])).exists()}
    spent = {task: value for task, value in spent.items() if task not in alive}
    return [Complaint(
        task, f"{rounds} builder answer{'s' if rounds > 1 else ''} never kept (${total:.2f} in all)",
        "read calls/<task>/ and salvage it, or say why it was right to drop")
        for task, (rounds, total) in sorted(spent.items())]
