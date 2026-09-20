"""Publish one validated molecule as notes, without changing the graph reader.

Every file this writes is an Obsidian note (`cardfile`), so the molecule a
reviewer accepted and the vault a person opens are the same files.
"""

from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile

GRAPH_LIB = pathlib.Path(__file__).resolve().parents[1] / "graph" / "lib"
sys.path.insert(0, str(GRAPH_LIB))
import cardfile  # type: ignore[import-not-found]
import durable  # type: ignore[import-not-found]
from backlog import Backlog  # type: ignore[import-not-found]
from prompts import moved_under  # type: ignore[import-not-found]
from slicer_law import assert_order, assert_recovered_order
from tree_stale import (  # this file stays the one door: `from tree import CardMoved`
    CardMoved,
    StaleChild,
    being_built,
    check,
    parent_digest,
    plan_digest,
    retire,
)


def publish(backlog: pathlib.Path, made: dict, target_id: str = "",
            started: dict | None = None) -> str:
    """Make the folder visible whole, then turn the replaced leaf into its parent.

    `started` is the target as the slicer read it before it planned. A hold
    raised since, or a contract edited since, is a person's decision newer than
    this molecule: settling the card under it would clear the hold or bury the
    edit. Checked inside the lock the publish already holds, and so is the whole
    prospective graph: the answer was validated against the backlog as it was,
    before a paid review, and another writer can land `M.a` in that window.
    """
    if not backlog.is_dir():
        raise ValueError("the slicer writes the tree backlog format only")
    name = made["name"]
    final = backlog / name
    book = Backlog(backlog)
    with book.only_writer():
        target = book.task(target_id) if target_id else None
        if target_id and not target:
            raise KeyError(f"no task {target_id} in {backlog}")
        if started is not None:
            moved = moved_under(target, started)
            if moved:
                raise CardMoved(moved)
        if target_id and being_built(target_id):
            raise CardMoved(f"a lane is building {target_id} right now")
        if target and target.get("status") == "sliced" \
                and name not in (target.get("needs") or []):
            raise ValueError(f"{target_id} already has a published child")
        material = dict(made)
        if target:
            # The writer owns lineage. A model may not weaken the prerequisites
            # the failed leaf had already declared.
            material["needs"] = list(target.get("needs") or [])
            # And the parent's contract as this child was planned for it: an
            # interrupted publish is finished from the child on disk, and lineage
            # alone would let a molecule settle a parent rewritten since.
            material["sliced_from_contract"] = parent_digest(target, name)
        if final.exists():
            check(final, target_id, target)
            # The molecule is already on disk, waits and all; what is still to
            # write is the parent's wait for it, and this is the last place the
            # whole graph is true. Read from the rows, never rebuilt from the
            # recovery's own empty answer — that erased the child's own waits.
            assert_recovered_order(name, book.tasks(), target or {})
        else:
            assert_order(name, made, book.tasks(), target)
            temporary = pathlib.Path(tempfile.mkdtemp(prefix=f".{name}.", dir=backlog))
            try:
                # Linked against the backlog it will sit in, never the staging
                # folder: a wait on another molecule is a link to that note.
                _write(temporary, material, target_id, cardfile.linker(backlog))
                temporary.replace(final)
            except BaseException:
                shutil.rmtree(temporary, ignore_errors=True)
                raise
        # The rename that gave the folder its name is a directory entry of its
        # own, and the settle below is durable: without this, power loss could
        # keep a parent marked `sliced` and lose the child that carries its work
        # — the files inside are no use while the entry naming them is still in
        # the page cache (Codex on finding 14). The recovery path syncs too: it
        # may be finishing a publish whose rename never landed either.
        durable._sync(backlog)   # as publishing.py does for the keep note
        if target is not None:
            needs = list(dict.fromkeys([*(target.get("needs") or []), name]))
            book.set_status(target_id, "sliced", needs=needs, refused_why=None,
                            blocked_by_human=None)
    return name


def recover(backlog: pathlib.Path, target_id: str) -> tuple[str, str]:
    """The slicer's recovery entry: the child settled, and the child retired.

    An interrupted publish is finished (`roll_forward`). A child that can never
    finish — planned for another version of this parent, or edited since it was
    reviewed — is retired instead, once: refusing it again cost nothing, so the
    same one was selected every run and the parent was never planned again
    (astra's round-4 finding 9). Both are "" when there was nothing to do.
    """
    try:
        return roll_forward(backlog, target_id), ""
    except StaleChild as stale:
        return "", retire(backlog, target_id, stale.child)


def roll_forward(backlog: pathlib.Path, target_id: str) -> str:
    """Finish the one child-folder publish whose parent update was interrupted."""
    book = Backlog(backlog)
    target = book.task(target_id)
    if not target or target.get("status") == "sliced":
        return ""
    children = [str(row["id"]) for row in book.tasks()
                if row.get("sliced_from") == target_id and row.get("id") != target_id]
    if len(children) > 1:
        raise ValueError(f"{target_id} has more than one published child")
    if not children:
        return ""
    publish(backlog, {"name": children[0], "needs": [], "atoms": []}, target_id)
    return children[0]


def _write(folder: pathlib.Path, made: dict, target_id: str, link=None) -> None:
    atoms = made["atoms"]
    head = {key: value for key, value in made.items() if key not in ("name", "atoms")}
    if target_id:
        head["sliced_from"] = target_id
    head["status"] = "sliced" if atoms else "todo"
    if not atoms:
        head["gate_reviewed_first"] = True
    _note(folder / cardfile.HEAD, head, link)
    for atom in atoms:
        body = {key: value for key, value in atom.items() if key not in ("name", "stage")}
        body["status"] = "todo"
        body["gate_reviewed_first"] = True
        _note(folder / f"{atom['stage']:02d}-{atom['name']}{cardfile.SUFFIX}", body, link)
    # The plan this folder was published with, digested from the folder itself
    # so recovery reads it exactly as it was written — which is why the head is
    # written twice: the digest is of the files, and it lands in one of them.
    # Still inside the staging directory, so the molecule appears whole or not
    # at all, and a crash never leaves a child that reads as edited.
    head["sliced_atoms"] = plan_digest(folder)
    _note(folder / cardfile.HEAD, head, link)


def _note(path: pathlib.Path, body: dict, link=None) -> None:
    # On the platter before the parent is settled over it: the parent's own
    # write is durable, so power loss between the two kept a card marked
    # `sliced` and lost the child that carries its work (astra round 3,
    # finding 14). `durable.replace` writes beside and renames, as this did.
    durable.replace(path, cardfile.dump(body, link))
