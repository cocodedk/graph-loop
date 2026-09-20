"""`graph-goal.py remember` — a node's memory, written from the campaign log.

Run by hand, after a driver has stopped. It is not a step: nothing the driver,
the supervisor or a hook runs so much as names this file, and a test in
`graph/tests` says so by reading the source rather than by believing this
sentence.

It reads the campaign's log and the backlog, and writes for every card that
card's memory relative — `<backlog>/<Molecule>/relatives/memory-<card>.md`,
and `memory-molecule.md` for the molecule itself. A relative lives in a
sub-folder because `molecule.ordered` reads every other `.md` in a molecule as
an atom and stops the whole backlog read on one it cannot number.

What makes it safe to run on a live vault:

- it points and never copies (`remember_events.py`), so the log stays the one
  home of the raw evidence;
- the note is a projection of the log — same log, same bytes — so running it
  twice writes nothing and throwing a note away costs nothing;
- it never touches the card, not even its front matter;
- a log it cannot make sense of is counted and stepped over, never raised on.
"""

from __future__ import annotations

import pathlib

import backlog_tree
import cardfile
import durable
import remember_log
import where
from remember_events import dated
from remember_note import ours, render
from workspace import Workspace

FOLDER = "relatives"
PREFIX = "memory-"
HAND = "kept: edited by hand"


def command_remember(args) -> int:
    space = Workspace(args.workspace or where.campaign())
    rows, lost = remember_log.rows(space)
    named = remember_log.backlog(rows)
    if not named:
        print("this campaign's log holds no init event that names a backlog; run "
              f"`init` first. {len(rows)} events read, {lost} lines could not be read")
        return 1
    root = pathlib.Path(named)
    if not root.is_dir():
        print(f"{root} is one file, not a tree of molecules: a memory relative lives "
              "in a molecule's own relatives/ folder, and this backlog has none")
        return 0
    counts = write_memory(root, rows)
    print(f"remember: {counts['written']} memory notes written, "
          f"{counts['unchanged']} already saying it, {counts['untouched']} not written "
          f"at all, under {root}")
    for name, concern in sorted(counts["said"].items()):
        print(f"  {name}: {concern}")
    print(f"  from {counts['events']} events — {counts['no_section']} of a kind this "
          f"note has no section for, {counts['not_a_card']} sections about a node the "
          f"backlog does not hold, {counts['unreadable']} it could not read"
          + (f", and {lost} log lines that could not be read at all" if lost else ""))
    return 0


def write_memory(root: pathlib.Path, rows: list) -> dict:
    """Refresh every card's memory from these events, and say what happened.

    Every note is written inside its own guard, encoding and all: one note the
    command cannot finish never costs the others.
    """
    memory, counts = dated(rows)
    paths = backlog_tree.read(root)[backlog_tree.PATHS]
    link = cardfile.linker(root)
    inside = root.resolve()
    done: set = set()
    counts.update(written=0, unchanged=0, untouched=0, said={}, events=len(rows),
                  not_a_card=sum(len(sections) for node, sections in memory.items()
                                 if node not in paths))
    for task_id, card in sorted(paths.items()):
        try:
            concern = _one(inside, done, card, link(task_id),
                           memory.get(task_id) or [], counts)
        except Exception as raised:  # noqa: BLE001 — one note never costs the rest
            counts["untouched"] += 1
            concern = f"writing it raised {type(raised).__name__}; nothing was changed"
        if concern:
            counts["said"][task_id] = concern
    return counts


def _one(inside: pathlib.Path, done: set, card: pathlib.Path, target: str,
         sections: list, counts: dict) -> str:
    """One card's memory refreshed, and what could not be done to it."""
    folder = card.parent / FOLDER
    note = folder / f"{PREFIX}{card.stem}{cardfile.SUFFIX}"
    unsafe = _unsafe(inside, done, card, folder, note)
    if unsafe:
        counts["untouched"] += 1
        return unsafe
    text = render(target, sections)
    raw = note.read_bytes() if note.exists() else None
    if raw is not None and raw == text.encode("utf-8"):
        counts["unchanged"] += 1
        return ""
    if raw is not None and not ours(raw, target):   # the one door, and it opens one way
        counts["untouched"] += 1
        return HAND
    # The same question again, with the new bytes already on the platter and
    # the rename one step away: what was read above is stale by now, and
    # somebody saving inside that moment had their edit renamed over.
    if durable.replace(note, text, guard=lambda: _still(note, raw)) is None:
        counts["untouched"] += 1
        return HAND
    counts["written"] += 1
    return ""


def _still(note: pathlib.Path, raw: bytes | None) -> bool:
    """Whether the file is still what the ownership check above saw: the same
    bytes, or still not there at all."""
    return (note.read_bytes() if note.exists() else None) == raw


def _unsafe(inside: pathlib.Path, done: set, card: pathlib.Path,
            folder: pathlib.Path, note: pathlib.Path) -> str:
    """Why this note must not be written.

    Two questions, because either alone lets a write escape. Where does the
    path REALLY lead — asked of the filesystem, of every ancestor at once, so a
    molecule folder that is itself a link cannot take its notes out of the
    vault. And is anything on the last stretch a link at all — because one
    pointing back INSIDE the vault resolves happily and would still land the
    write on a card. `durable.replace` writes `.<name>.tmp` beside the note and
    renames it into place, so that name is a target as much as the note is.
    """
    piece = card.parent
    if piece.is_symlink():
        # It may resolve inside the vault or out of it, and neither is a
        # reason to write: under this name the notes would carry this name's
        # backlinks into another molecule's folder, and the molecule that
        # really lives there would then find a note that is not its own and
        # keep it — losing its history to a link somebody made.
        return (f"{piece.name} is a symlink to another folder, so nothing is exported "
                "under this name")
    real = note.resolve()
    if real in done:
        return f"{piece.name} holds the note another name in this backlog already wrote"
    done.add(real)
    beside = folder / f".{note.name}.tmp"
    for path in (folder, note, beside):
        if path.is_symlink():
            return f"{path.name} is a symlink, and nothing here is written through one"
        if not _within(inside, path):
            return f"{path.name} resolves outside the vault; nothing there was written"
    if folder.exists() and not folder.is_dir():
        return f"{folder.name} is not a folder; nothing here was changed"
    if beside.exists():
        return (f"{beside.name} is already there, and the durable write would replace "
                "it; nothing here was changed")
    return ""


def _within(inside: pathlib.Path, path: pathlib.Path) -> bool:
    """Whether this path really lies in the vault. `resolve` answers for every
    ancestor, and for a path that is not there yet it answers for the part
    that is."""
    try:
        return path.resolve().is_relative_to(inside)
    except OSError:
        return False
