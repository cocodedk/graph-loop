"""Cutting one task into smaller ones, inside the caller's write lock.

Split from `backlog` at the 200-line cap. `Backlog.slice_task` is still the
front door; this is only the part that rearranges the rows.
"""

from __future__ import annotations

from backlog_status import INHERITED, RUNNABLE


def slice_rows(document: dict, task_id: str, pieces: list[dict], where: str) -> list[str]:
    """Replace one task with smaller ones that carry its dependencies.

    The parent keeps its id and becomes the piece everything downstream still
    waits for: its `needs` grow to include every piece, so nothing that
    depended on the parent can start early.
    """
    rows = document.get("tasks") or []
    index = next((i for i, row in enumerate(rows) if row.get("id") == task_id), None)
    if index is None:
        raise KeyError(f"no task {task_id} in {where}")
    parent = rows[index]
    ids = []
    for number, piece in enumerate(pieces, start=1):
        new = dict(piece)
        new["id"] = f"{task_id}.{number}"
        new.setdefault("status", RUNNABLE)
        new.setdefault("needs", list(parent.get("needs") or []))
        new.setdefault("sliced_from", task_id)
        for carried in INHERITED:
            # A piece that does not say otherwise keeps what the parent declared
            # about itself. gate_files_are_the_work was lost here, and a piece
            # whose gate runs its own test is refused at the scope check before
            # a builder is ever paid for.
            if carried not in new and carried in parent:
                new[carried] = parent[carried]
        ids.append(new["id"])
        rows.insert(index + number, new)
    parent["needs"] = sorted(set(parent.get("needs") or []) | set(ids))
    parent["status"] = "sliced"
    return ids
