#!/usr/bin/env python3
"""Turn the one-file backlog into a tree of molecules, once.

    python3 graph/to-tree.py <backlog.yaml> <new vault>

A task whose id is the prefix of others is a molecule and they are its atoms;
every other task is a molecule of one. Ids do not change: the folder is the
piece's id and the file's stem is the rest of the atom's.

The number in front of each atom is its stage, computed from the `needs` the
file already declares: one more than the furthest thing it waits for inside
its own molecule. Atoms that waited for nothing in the molecule share stage 1
and run side by side. This is a conservative reading — an atom also comes to
wait for the others in the stage below it, which can only make it start later,
never sooner — and the tree writes that order down once, in the file names.

Every file it writes is an Obsidian note (`cardfile`), so the tree it makes is
the vault a person opens.

Nothing is deleted: the old file stays as the archive.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
import cardfile  # type: ignore[import-not-found]
import yaml  # type: ignore[import-untyped]  # no stubs in this environment

DERIVED = ("id", "needs", "sliced_from")


def molecules(rows: list[dict],
              standalone: set[str] | frozenset[str] = frozenset()) -> dict[str, list[dict]]:
    """Each piece with its atoms, in the order the file lists them.

    An id in `standalone` becomes a molecule of one whatever its prefix says:
    the stage blanket would hand it waits it never declared, so it keeps its
    exact `needs` in its own folder instead."""
    ids = {row["id"] for row in rows}
    out: dict[str, list[dict]] = {row["id"]: [] for row in rows
                                  if row["id"] in standalone
                                  or "." not in row["id"] or row["id"].split(".")[0] not in ids}
    for row in rows:
        head = row["id"].split(".")[0]
        if row["id"] in out:
            continue
        if head not in out:
            raise KeyError(f"{row['id']} belongs to {head}, which is not a task")
        out[head].append(row)
    return out


def stages(piece: str, atoms: list[dict]) -> dict[str, int]:
    """Each atom's stage: one past the furthest thing it waits for in here."""
    inside = {row["id"] for row in atoms}
    depth: dict[str, int] = {}

    def of(task_id: str) -> int:
        if task_id not in depth:
            depth[task_id] = 0                            # a cycle stops here, at stage 1
            row = next(row for row in atoms if row["id"] == task_id)
            depth[task_id] = 1 + max(
                [of(name) for name in row.get("needs") or [] if name in inside] or [0])
        return depth[task_id]

    for row in atoms:
        of(row["id"])
    return depth


def write(root: pathlib.Path, rows: list[dict],
          standalone: set[str] | frozenset[str] = frozenset()) -> None:
    for piece, atoms in molecules(rows, standalone).items():
        folder = root / piece
        folder.mkdir(parents=True)
        head = next(row for row in rows if row["id"] == piece)
        _note(folder / cardfile.HEAD, head, piece, {row["id"] for row in atoms} | {piece})
        depth = stages(piece, atoms)
        for row in atoms:
            stem = row["id"][len(piece) + 1:]
            _note(folder / f"{depth[row['id']]:02d}-{stem}{cardfile.SUFFIX}", row, piece,
                  {other["id"] for other in atoms} | {piece})


def _note(path: pathlib.Path, row: dict, piece: str, inside: set[str]) -> None:
    body = {key: value for key, value in row.items() if key not in DERIVED}
    if row.get("sliced_from") not in (None, piece):
        body["sliced_from"] = row["sliced_from"]
    outside = [name for name in row.get("needs") or [] if name not in inside]
    if outside:
        body["needs"] = outside
    path.write_text(cardfile.dump(body), "utf-8")


def faithful(source: pathlib.Path, target: pathlib.Path) -> set[str]:
    """Convert, read the tree back, and extract every card whose reconstructed
    `needs` differ from what the file declared — until the tree says exactly
    what the file said. Returns the extracted ids."""
    import shutil

    import backlog_tree  # type: ignore[import-not-found]

    rows = yaml.safe_load(source.read_text("utf-8"))["tasks"]
    out: set[str] = set()
    for _ in range(len(rows)):
        if target.exists():
            shutil.rmtree(target)
        write(target, rows, out)
        wrong = differs(rows, backlog_tree.read(target)["tasks"]) - out
        if not wrong:
            return out
        out |= wrong
    raise SystemExit("the tree still disagrees with the file after extracting everything")


def differs(rows: list[dict], seen: list[dict]) -> set[str]:
    """Ids whose tree row does not say what the file said, in ANY declared
    field. A parent of atoms is exempt only in its derived `needs` — its goal,
    status or session drifting is still drift."""
    parents = {row["id"]: {a["id"] for a in rows
                           if a["id"].startswith(row["id"] + ".")}
               for row in rows
               if any(a["id"].startswith(row["id"] + ".") for a in rows)}

    def shape(row: dict, parent: bool) -> dict:
        body = {key: value for key, value in row.items()
                if key not in DERIVED and value not in (None, [], "")}
        needs = set(row.get("needs") or [])
        # a parent's derived waits on its own atoms are not drift;
        # its DECLARED external needs still are
        body["needs"] = needs - parents[row["id"]] if parent else needs
        return body

    declared = {row["id"]: shape(row, row["id"] in parents) for row in rows}
    return {row["id"] for row in seen
            if row["id"] in declared
            and shape(row, row["id"] in parents) != declared[row["id"]]}


if __name__ == "__main__":
    source, target = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    if target.exists():
        sys.exit(f"{target} is already there; move it aside first")
    apart = faithful(source, target)
    print(f"{len(list(target.iterdir()))} molecules in {target}"
          + (f"; extracted whole: {sorted(apart)}" if apart else ""))
