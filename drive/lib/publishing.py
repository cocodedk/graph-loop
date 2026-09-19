"""Reconciling the campaign branch at the top of a turn.

Split out of `drive-goal.py` to keep it under the file's own size limit.
"""

from __future__ import annotations

import json
import pathlib

import durable
import keep_pending
from contract import revision
from keep_remote import behind
from workspace_claims import _now

KEEPS = "keeps"       # where a superseded keep's receipt is written


def reconcile(loop, book, space) -> None:
    """A crash between the branch move and the card write leaves a commit the
    branch already holds with no card to show for it: closed here, before
    anything else starts — unless the card was decided again in the meantime.
    Whatever decided it after the keep is newer than the keep, so a card whose
    revision no longer matches the one the keep was made against is written off
    mechanically (`supersede`) rather than handed to a person. Then, if the
    branch still holds commits origin does not — the last keep of a run has no
    later keep to carry a failed push — one more push is tried, so a run never
    ends with only an alert to show for it."""
    for task_id, commit in (loop.keeper.pending() if loop.keeper else []):
        # ONE lock hold for the read, the check and the write: a decision that
        # lands between any two of them is read too early and written over a
        # moment later, which is the fault this check exists to stop. The push
        # below is outside it — nothing about the branch needs the backlog.
        with book.only_writer():
            card = book.task(task_id) or {}
            kept_against = str(card.get("keep_revision") or "")
            # An ABSENT revision is unbound, never a match: a note from before
            # the field existed, or a card the keep's own write never reached,
            # says nothing about which card the commit was made for — and the
            # card in front of it may have been dropped or rewritten since.
            if kept_against != revision(card):
                supersede(loop, space, task_id, commit, kept_against, revision(card))
                continue
            existing = next((row for row in space.events() if row.get("kind") == "accepted"
                             and row.get("task") == task_id and row.get("commit") == commit), None)
            when = existing["at"] if existing else space.event(
                "accepted", task=task_id, commit=commit,
                why="the branch held this keep; its card-write was lost")["at"]
            book.set_status(task_id, "done", commit=commit, kept_at=when)
        failed = loop.keeper.push()
        if failed:
            space.alert(task_id, f"reconciled {commit[:8]} but not pushed: {failed}")
        loop.keeper.settle(task_id)
    if loop.keeper and behind(loop.keeper.repo, loop.keeper.branch):
        failed = loop.keeper.push()
        if not failed:
            space.event("pushed", branch=loop.keeper.branch,
                       why="the branch had commits origin did not hold at the turn top")
            return
        message = f"the branch has commits origin does not hold and the push failed: {failed}"
        key = " ".join(message.split())[:300]
        if not any(key in line for line in space.alerts()):
            space.alert("the campaign", message)


def receipt_path(space, task_id: str, commit: str) -> pathlib.Path:
    """The receipt for one superseded keep. One name per card and commit, so a
    replay writes the same record rather than a second one."""
    return pathlib.Path(space.root) / KEEPS / f"{task_id}-{commit[:12]}.json"


def supersede(loop, space, task_id: str, commit: str, kept_at: str, now: str) -> None:
    """Write a keep the card has outgrown down, then retire that exact note.

    The receipt is on the platter BEFORE the note goes, so a death between the
    two leaves a record saying what is still owed and `settle_superseded`
    finishes it. Nothing else moves: the commit stays on the branch, the newer
    card keeps whatever decided it, and no card that has already finished is
    reopened to settle a note.
    """
    path = receipt_path(space, task_id, commit)
    note = keep_pending.note_path(loop.keeper.repo, loop.keeper.branch, task_id)
    durable.replace(path, json.dumps(
        {"task": task_id, "commit": commit, "kept_at_revision": kept_at,
         "card_revision": now, "note": str(note), "at": _now(), "settled": ""},
        sort_keys=True, indent=1))
    space.event("keep_superseded", task=task_id, commit=commit,
                kept_at_revision=kept_at, card_revision=now,
                why=f"the branch holds {commit[:8]} for this card and "
                    + ("the card was decided again after that keep" if kept_at else
                       "the keep names no card revision, so nothing proves the card in "
                       "front of it is the one it was made for")
                    + "; both stand and the note is retired")
    _retire(path)


def settle_superseded(space) -> None:
    """Finish a retirement the loop died in the middle of, before any keep is
    reconciled again: a note the driver has already written off must not meet
    ordinary reconciliation a second time, because a card that has since moved
    back to the revision of the keep would then be closed on it."""
    for path in sorted((pathlib.Path(space.root) / KEEPS).glob("*.json")):
        if not json.loads(path.read_text("utf-8")).get("settled"):
            _retire(path)


def _retire(path: pathlib.Path) -> None:
    """Retire the note this receipt names, and mark the receipt settled.

    Only that note, and only while it still names this commit: a later keep for
    the same card writes its own note, and taking that one would lose a keep
    nobody has reconciled yet.

    A note nobody could READ is not a note that is gone. Only "there is no such
    file" is an answer; any other failure is raised and the receipt stays owed,
    because marking it settled would leave the note standing with nothing left
    to retire it (Codex, finding 2).

    The removal is a directory entry, and an entry that never reached the
    platter comes back: the parent is fsynced before the settlement is
    recorded, whether this call removed the note or found it already gone —
    the unlink that did remove it may itself have died in the page cache
    (Codex, finding 1).
    """
    row = json.loads(path.read_text("utf-8"))
    note = pathlib.Path(str(row.get("note") or ""))
    try:
        held = note.read_text("utf-8").strip()
    except FileNotFoundError:
        held = ""
    if held == row.get("commit"):
        note.unlink()
    if note.parent.is_dir():
        durable._sync(note.parent)
    durable.replace(path, json.dumps({**row, "settled": _now()}, sort_keys=True, indent=1))
