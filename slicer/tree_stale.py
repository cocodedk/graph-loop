"""Whether a child folder on disk is still the publication that was reviewed.

Split from `tree` at the 200-line cap; `tree` stays the one door and re-exports
these. Recovery finishes an interrupted publish from the folder it finds, so
what that folder is bound to is the whole of its authority: the parent it was
planned for, and the plan a reviewer read inside it.

A stale one is RETIRED rather than refused again. The refusal costs nothing and
changes nothing, so the same stale child was selected every run and its parent
stayed the slicer's for ever (astra's round-4 finding 9).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import pathlib
import sys
import tempfile

GRAPH_LIB = pathlib.Path(__file__).resolve().parents[1] / "graph" / "lib"
sys.path.insert(0, str(GRAPH_LIB))
import backlog_tree  # type: ignore[import-not-found]
import cardfile  # type: ignore[import-not-found]
import durable  # type: ignore[import-not-found]
import molecule  # type: ignore[import-not-found]
from backlog import Backlog  # type: ignore[import-not-found]
from contracts import ATOM, BASE
from prompts import contract_digest  # type: ignore[import-not-found]

RETIRED = "retired.txt"     # why the folder beside it was taken out of the way
# What the slicer's own answer declares, minus what the tree derives from where
# a file sits: `PLAN` is the molecule as it was reviewed, and nothing else.
PLAN = (BASE | ATOM) - set(backlog_tree.DERIVED) - {"name", "stage", "atoms"}


class CardMoved(RuntimeError):
    """The target changed under the slicer while it planned. Not a ValueError:
    the caller must not answer it with another paid planner round."""


class StaleChild(CardMoved):
    """A child publication that can never be finished: it was planned for
    another version of its parent, or its own plan has been edited since a
    reviewer read it. Retired once, never selected again."""

    def __init__(self, child: str, why: str):
        super().__init__(why)
        self.child = child


def being_built(target_id: str) -> bool:
    """Whether a lane holds this card at this moment.

    The card the slicer chose can be requeued and started while it plans, and a
    hold or a contract edit is not what that looks like — `moved_under` sees
    nothing. The claims file is the campaign's truth about now, kept current by
    every wave the driver runs, so it is read here rather than trusting the list
    of cards the slicer was handed hours earlier. No campaign (a slicer run by
    hand) means nobody is building anything.
    """
    import intelligence
    if intelligence.CAMPAIGN is None:
        return False
    from workspace import Workspace  # type: ignore[import-not-found]
    return target_id in Workspace(intelligence.CAMPAIGN).claimed_now()


def parent_digest(target: dict, child: str) -> str:
    """The parent's contract as it stood when `child` was planned for it.

    The publish itself adds the child to the parent's `needs`, and `needs` is
    part of the contract — so the child is taken back out before digesting, and
    a molecule written and one recovered are compared by the same reading.
    """
    return contract_digest(
        {**target, "needs": [wait for wait in (target.get("needs") or []) if wait != child]})


def plan_digest(folder: pathlib.Path) -> str:
    """The plan inside this folder, as one short name: every file it holds, in
    the order the folder declares, read for the fields `PLAN` names and for the
    waits it states.

    A card that has STARTED is still the molecule that was reviewed — status and
    the rounds it has spent are not the plan — while a goal, a gate, a done-when
    or a WAIT somebody changed is a molecule nobody read: an atom that no longer
    waits for the card making what it uses starts before it (an independent review,
    finding 3).

    The waits are normalised because the tree writes some of them itself: the
    molecule's own outside waits are copied into the first stage's files on the
    next write, and the stage numbers carry the rest (`backlog_tree.read`), so
    what is compared is what each file STATES beyond them.
    """
    head = cardfile.load(folder / cardfile.HEAD)
    outside = {str(one) for one in head.get("needs") or []}
    plan = [[cardfile.HEAD, _stated(head), sorted(outside)]]
    for path in molecule.ordered(folder):
        body = cardfile.load(path)
        plan.append([path.name, _stated(body),
                     sorted({str(one) for one in body.get("needs") or []} - outside)])
    return hashlib.sha256(
        json.dumps(plan, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _stated(body: dict) -> dict:
    return {key: body[key] for key in sorted(body) if key in PLAN}


def check(folder: pathlib.Path, target_id: str, target: dict | None) -> None:
    """Raise unless this folder is the publication that was reviewed for this
    parent, and nothing else.

    Lineage says which card a molecule was cut from; it does not say which
    VERSION of that card, nor that the molecule is still the one a reviewer
    read. A parent rewritten since — by a person, a replan, a slicer's rewrite
    — is a contract this molecule was never planned against, and settling it
    here would bury the new one. A molecule that names no contract at all, or
    no plan of its own, is unbound, which is not a match either.
    """
    if not target_id:
        raise FileExistsError(f"molecule {folder.name} already exists")
    body = cardfile.load(folder / cardfile.HEAD)
    if body.get("sliced_from") != target_id:
        raise FileExistsError(f"molecule {folder.name} belongs to another slice")
    bound = str(body.get("sliced_from_contract") or "")
    if bound != parent_digest(target or {}, folder.name):
        raise StaleChild(folder.name,
                         f"{folder.name} was planned for another version of {target_id}: "
                         f"its contract has changed since ({bound or 'nothing'} bound)")
    try:
        plan = plan_digest(folder)
    except (OSError, ValueError) as unreadable:
        raise StaleChild(folder.name, f"{folder.name} cannot be read as the molecule it "
                                      f"was published as: {unreadable}") from unreadable
    if str(body.get("sliced_atoms") or "") != plan:
        raise StaleChild(folder.name, f"{folder.name} is not the molecule that was reviewed: "
                         f"its own plan has changed since "
                         f"({body.get('sliced_atoms') or 'nothing'} bound)")


def retire(backlog: pathlib.Path, target_id: str, name: str) -> str:
    """Take a stale child publication out of the reader's way; say where it went.

    Asked again under the lock that renames, because the answer can have
    changed: a parent rewritten back, or a publish another writer finished, is
    not stale at all, and nothing is retired then ("" comes back).

    The folder is kept whole under a dot-name, which `backlog_tree.read` does
    not read — the plan somebody paid for survives, the parent is free to be
    sliced again, and the rename IS the receipt recovery reads next time, since
    there is no child left to select. A lane building any card inside it holds
    the whole molecule: that is work in flight, not a stale plan.

    The parent's wait for it goes in the same hold. A publish that settled the
    parent wrote that wait, and re-parking the card kept it, so the parent was
    left waiting for a card that no longer exists — and the next child, whose
    waits are the parent's, inherited the same broken ring (an independent review,
    finding 4).

    The wait is released BEFORE the rename: only that order survives an
    interruption. Renaming first and dying leaves a parent waiting for a folder
    already gone, and no later pass notices, because the child it would call
    stale is not there. Dying the other way leaves the child readable and the
    parent free, and the next pass retires it — the same end state (Codex on
    f1ae4c0f, finding 1).
    """
    book = Backlog(backlog)
    folder = backlog / name
    with book.only_writer():
        parent = book.task(target_id)
        try:
            check(folder, target_id, parent)
        except StaleChild as stale:
            why = str(stale)
        else:
            return ""
        held = [one for one in _ids(folder) if being_built(one)]
        if held:
            raise CardMoved(f"a lane is building {', '.join(held)} right now")
        (folder / RETIRED).write_text(f"{why}\n", "utf-8")
        waits = [one for one in (parent or {}).get("needs") or [] if one != name]
        if waits != ((parent or {}).get("needs") or []):
            book.note(target_id, needs=waits)     # durable, and BEFORE the rename
        retired = pathlib.Path(tempfile.mkdtemp(prefix=f".stale-{name}.", dir=backlog))
        folder.replace(retired)
        durable._sync(backlog)     # the entry that names it, as `publish` syncs its own
    return retired.name


def _ids(folder: pathlib.Path) -> list[str]:
    """Every card id this folder holds: the molecule, and each atom in it."""
    ids = [folder.name]
    with contextlib.suppress(ValueError):     # a folder nobody can read holds no atom
        ids += [molecule.atom_id(folder.name, path.name)
                for path in molecule.ordered(folder)]
    return ids
