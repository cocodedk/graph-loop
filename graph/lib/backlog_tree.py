"""A backlog kept as a tree: one folder per molecule, one file per atom.

    backlog/
      T26/
        molecule.md       the piece itself — what it is for, and its own status
        01-schema.md      the field exists
        02-producer.md    the record carries it
        03-reader.md      the rule reads it
      T25/
        molecule.md       a molecule of one is a folder with no atoms

Every file is one Obsidian note (`cardfile`), so the backlog and the vault a
person reads are the same files.

`molecule.md` IS the parent card: its id is the folder's name, so `T26` and
`T26.schema` read exactly as they did when the backlog was one file, and every
`needs` that names them still points at them.

Nothing is written down twice. The order is the numbers in the file names: an
atom waits for every atom with a lower number, so `01, 02, 03` is one after
another and `01, 02, 02` is one and then two side by side. The piece waits for
all of them, and each atom knows it was sliced from the folder it sits in.
A molecule appears whole or not at all,
because it is built under a dot-name and renamed into place, and a dot-name is
not read; otherwise atom 01 can start before its siblings exist.
"""

from __future__ import annotations

import pathlib

import cardfile
import durable
import molecule

PATHS = "_paths"     # id → file: put here by read, taken out again by write
DERIVED = ("id", "needs", "sliced_from")   # read from where the atom sits


def read(root: pathlib.Path) -> dict:
    tasks, paths = [], {}
    for folder in sorted(root.iterdir()):
        head = folder / cardfile.HEAD
        if not folder.is_dir() or folder.name.startswith(".") or not head.exists():
            continue
        parent = cardfile.load(head)
        parent["id"] = folder.name
        outside = list(parent.get("needs") or [])
        pieces: list[dict] = []
        stage: int | None = None
        ahead: list[str] = []
        for path in molecule.ordered(folder):
            if molecule.stage(path.name) != stage:
                stage, ahead = molecule.stage(path.name), [row["id"] for row in pieces]
            row = cardfile.load(path)
            row["id"] = molecule.atom_id(folder.name, path.name)
            # Inside the molecule the numbers ARE the dependency. A `needs` an
            # atom writes down is outside it, and it keeps the piece's own.
            row["needs"] = (ahead or outside) + \
                           [name for name in (row.get("needs") or []) if name not in outside]
            row.setdefault("sliced_from", folder.name)
            paths[row["id"]] = path
            pieces.append(row)
        # The piece waits for every atom, as a sliced task always has.
        parent["needs"] = outside + [row["id"] for row in pieces]
        paths[parent["id"]] = head
        tasks.append(parent)
        tasks.extend(pieces)
    return {"tasks": tasks, PATHS: paths}


def write(root: pathlib.Path, document: dict) -> None:
    paths = document.pop(PATHS, None) or {}
    link = cardfile.linker(root)
    for row in document.get("tasks") or []:
        path = paths.get(row.get("id"))
        if path is None:
            raise KeyError(
                f"{row.get('id')} has no file in {root}: a tree backlog gains atoms by "
                "writing a molecule, never by adding a row to the list")
        body = {key: value for key, value in row.items() if key not in DERIVED}
        if row.get("sliced_from") not in (None, path.parent.name):
            body["sliced_from"] = row["sliced_from"]   # a piece cut from another piece
        kept = _outside(row, path)
        if kept:
            body["needs"] = kept
        _one(path, body, link)


def _one(path: pathlib.Path, body: dict, link) -> None:
    """Write this card's file, touching the body only when the body changed.

    The loop's own transitions — `status` at each one, a triage verdict, the
    tree it is building in — are front matter, and they are patched into the
    note line by line. A person's prose, their headings and their links come
    back byte for byte, which is what makes the note safe to keep open in
    Obsidian while the loop runs.
    """
    was = path.read_text("utf-8")
    read = cardfile.parse(was)
    if any(read.get(key) != body.get(key) for key in cardfile.BODY):
        encoded = cardfile.dump(body, link).encode("utf-8")
        if path.read_bytes() != encoded:
            durable.replace(path, encoded)
        return
    text = was
    for key in dict.fromkeys([*read, *body]):
        if key not in cardfile.BODY and read.get(key) != body.get(key):
            text = cardfile.patch(text, key, body.get(key))
    if text != was:      # 112 molecules must not pay for one card's status write
        durable.replace(path, text)


def _outside(row: dict, path: pathlib.Path) -> list:
    """The `needs` this file has to keep: everything the tree does not derive.

    Derived means an atom IN THIS FOLDER — the stage numbers rebuild those. A
    name that merely starts with the folder's name is not necessarily one: a
    piece cut into its own molecule (`T6.approver` beside `T6`) is a sibling
    file, and the reader rebuilds nothing for it. Trusting the prefix dropped
    every such link on the first write and settled three sliced parents on
    children that were never built (2026-09-01).
    """
    inside = {path.parent.name}
    for atom in molecule.ordered(path.parent):        # the one atom reader, as `read` uses
        inside.add(molecule.atom_id(path.parent.name, atom.name))
    return [name for name in row.get("needs") or [] if name not in inside]


def after_write(root: pathlib.Path, task_id: str, needs: list) -> dict[str, list]:
    """Every card in this molecule whose waits the next read would give back
    differently if `needs` were written to this card's file.

    `write` keeps only the names the tree does not derive and `read` puts the
    derived ones back, so an edit to `needs` is not stored as it is stated: an
    atom cannot drop the atoms it runs behind, nor the molecule's own waits it
    inherits in the first stage, and it cannot add a wait on an atom of its own
    molecule that runs later; the molecule cannot drop its atoms either. A
    rewrite is checked against this, or the tree restores a circle the check
    never saw (astra round 4, finding 4).

    And writing one file moves more than one card: a molecule's own `needs` ARE
    what its first-stage atoms inherit, so re-aiming them re-aims every atom in
    the folder — a rewrite judged on the written card alone put a circle through
    an atom nobody had looked at (an independent review).

    Read from the FOLDER, through the atom reader `read` and `write` both use —
    never from the id or from `sliced_from`, because an atom cut from another
    atom sits in the folder and says neither (`_outside`).
    """
    path = read(root)[PATHS].get(task_id)
    if path is None:
        return {task_id: list(needs)}     # not a card this tree holds
    folder = path.parent
    atoms = molecule.ordered(folder)
    ids = [molecule.atom_id(folder.name, atom.name) for atom in atoms]
    kept = _outside({"needs": needs}, path)      # what the file would really store
    head = cardfile.load(folder / cardfile.HEAD)
    outside = kept if path.name == cardfile.HEAD else list(head.get("needs") or [])
    moved = {folder.name: outside + ids}         # the piece waits for every atom
    for atom, atom_id in zip(atoms, ids):
        body = cardfile.load(atom)
        own = kept if atom_id == task_id else list(body.get("needs") or [])
        moved[atom_id] = _ahead(atoms, ids, atom_id, outside) + \
            [name for name in own if name not in outside]
    return moved


def _ahead(atoms: list[pathlib.Path], ids: list[str], task_id: str,
           outside: list) -> list:
    """What this atom runs behind, as `read` derives it: every atom of an
    earlier stage, or the molecule's own waits while there is no earlier one."""
    seen: list[str] = []
    stage: int | None = None
    ahead: list = list(outside)
    for atom, atom_id in zip(atoms, ids):
        if molecule.stage(atom.name) != stage:
            stage, ahead = molecule.stage(atom.name), list(seen) or list(outside)
        if atom_id == task_id:
            break
        seen.append(atom_id)
    return ahead
