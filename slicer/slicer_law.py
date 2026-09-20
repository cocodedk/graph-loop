"""Naming, file creation and ancestry rules shared by every generated leaf."""

from __future__ import annotations

import pathlib
import sys

from slicer_graph import _assert_no_cycle, _graph

DRIVE_LIB = pathlib.Path(__file__).resolve().parents[1] / "drive" / "lib"
sys.path.insert(0, str(DRIVE_LIB))
import molecule as names  # type: ignore[import-not-found]


def assert_wall(task: dict) -> None:
    """The ONE wall definition lives in backlog_status.is_wall (shared with
    the turn-top hook); a triage verdict is honored when present and tolerated
    as absent until the triage component exists."""
    from backlog_status import is_wall  # type: ignore[import-not-found]
    if not is_wall(task):
        raise ValueError(f"{task.get('id')} is not a stuck CODE card the slicer may take")


def available(leaves: list[dict], repo: pathlib.Path) -> None:
    look, prior, prior_files = names.present(repo), set(), set()
    staged: dict[int, list[dict]] = {}
    for leaf in leaves:
        staged.setdefault(int(leaf.get("stage") or 1), []).append(leaf)
    for stage in sorted(staged):
        created_here: set[str] = set()
        files_here: set[str] = set()
        for leaf in staged[stage]:
            missing = [path for path in leaf["files"]
                       if path not in prior_files and not (repo / path).exists()]
            if missing and not leaf.get("may_add_files"):
                raise ValueError("a task that creates a file requires may_add_files: true: "
                                 + ", ".join(missing))
            own = set(leaf.get("creates") or [])
            for name in own:
                names.split(name)
            for name in leaf.get("uses") or []:
                names.split(name)
                if name not in prior and name not in own and not look(name):
                    raise ValueError(f"{leaf.get('name', 'molecule')} uses unavailable name {name}")
            created_here |= own
            files_here |= set(leaf["files"])
        prior |= created_here
        prior_files |= files_here


def lineage(target: dict, rows: list[dict]) -> list[dict]:
    by_id = {str(row.get("id")): row for row in rows}
    out, seen = [], set()
    current: dict | None = target
    while current and str(current.get("id")) not in seen:
        seen.add(str(current.get("id")))
        out.append(current)
        parent = str(current.get("sliced_from") or "")
        current = by_id.get(parent) if parent and parent not in seen else None
    return out


def signature(task: dict) -> tuple:
    clean = lambda value: " ".join(str(value or "").split())
    return (clean(task.get("goal")), tuple(sorted(task.get("files") or [])),
            clean(task.get("gate")), clean(task.get("done_when")))


def assert_order(name: str, made: dict, rows: list[dict], target: dict | None) -> None:
    """Every id this molecule publishes is new, and no wait runs in a circle.

    The tree derives an atom's id from where it sits — `molecule.atom_id` in
    `backlog_tree.read` — so a free molecule name can still land an atom on top
    of a card cut into its own folder; and it derives the waits from the stage
    numbers, so an atom may name the very leaf it replaces: `old` waits for
    `smaller`, `smaller` for `smaller.first`, `smaller.first` for `old`, and
    none of the three ever becomes ready. Both are read off the whole
    prospective graph here, before a file is written (SLICER.md:171-173,
    unique ids; SLICER.md:253, no cycle). Called twice: once by `validate`,
    which saves a paid review, and again by `tree.publish` inside the backlog
    lock, because a paid review takes minutes and another writer can claim an
    id in them. `assert_recovered_order` is the same question asked of a
    molecule that is already on disk.
    """
    graph, ids = _graph(name, made, rows, target)
    for claimed in [name, *ids]:
        if claimed in {str(row.get("id")) for row in rows}:
            raise ValueError(f"{claimed} already exists")
    _assert_no_cycle(graph)




def assert_recovered_order(name: str, rows: list[dict], target: dict) -> None:
    """The same graph question, for a molecule that is already published.

    Finishing an interrupted publish, the ids are claimed — by this molecule
    itself — and every wait it left behind is already on disk and read back with
    it. So the graph is the rows AS THEY STAND plus the one edge still to write:
    the parent's wait for its child. Rebuilding the child's waits from the
    recovery's own answer erased them instead, and a circle running through its
    atoms was invisible (Codex, round 3, on finding 13).
    """
    graph = {str(row.get("id")): list(row.get("needs") or []) for row in rows}
    graph[str(target["id"])] = list(target.get("needs") or []) + [name]
    _assert_no_cycle(graph)




# The file-ownership law lives next door; this file stays its one door.
from slicer_owners import assert_one_owner  # noqa: F401 — split at the cap
