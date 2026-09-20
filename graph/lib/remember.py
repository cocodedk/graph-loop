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

import cardfile
import durable
import molecule
import remember_log
import where
from remember_events import dated
from remember_note import ours, render
from remember_safe import still, unsafe
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
    counts.update(written=0, unchanged=0, untouched=0, said={}, events=len(rows))
    paths = _cards(root, counts)
    link = cardfile.linker(root)
    inside = root.resolve()
    done: set = set()
    counts["not_a_card"] = sum(len(sections) for node, sections in memory.items()
                               if node not in paths)
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


def _cards(root: pathlib.Path, counts: dict) -> dict:
    """Every card this command may write a memory for: its id and its file.

    Read from the folders and the file names alone — no card's contents are
    ever parsed here. `backlog_tree.read` does parse them, and one note that
    is not a card took the whole command down with it; a molecule whose atoms
    will not read is this command's to step over, not to raise on.

    A folder that is a symlink is refused BEFORE anything inside it is opened:
    where it leads is not the question, and its own `molecule.md` need not
    even be a card for the answer to be no.
    """
    found: dict = {}
    for folder in sorted(root.iterdir()):
        head = folder / cardfile.HEAD
        if folder.name.startswith(".") or not folder.is_dir():
            continue
        if folder.is_symlink():
            counts["untouched"] += 1
            counts["said"][folder.name] = ("it is a symlink to another folder, so "
                                           "nothing is exported under this name")
            continue
        if not head.exists():
            continue
        try:
            atoms = molecule.ordered(folder)
        except (OSError, ValueError) as unreadable:
            counts["untouched"] += 1
            counts["said"][folder.name] = (f"its atoms could not be read, so none of "
                                           f"them was written: {unreadable}")
            continue
        found[folder.name] = head
        for atom in atoms:
            found[molecule.atom_id(folder.name, atom.name)] = atom
    return found


def _one(inside: pathlib.Path, done: set, card: pathlib.Path, target: str,
         sections: list, counts: dict) -> str:
    """One card's memory refreshed, and what could not be done to it."""
    folder = card.parent / FOLDER
    note = folder / f"{PREFIX}{card.stem}{cardfile.SUFFIX}"
    refused = unsafe(inside, done, card, folder, note)
    if refused:
        counts["untouched"] += 1
        return refused
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
    try:
        put = durable.replace(note, text, guard=lambda: still(note, raw), exclusive=True)
    except OSError:
        # The sibling name was taken, or it was a link this refused to open.
        # Either way something else is using it and nothing here is guessed.
        counts["untouched"] += 1
        return "kept: a temp file was in the way"
    if put is None:
        counts["untouched"] += 1
        return HAND
    counts["written"] += 1
    return ""
