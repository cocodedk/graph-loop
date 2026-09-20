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
import where
from campaign_of import backlog_of
from remember_events import dated
from remember_note import aimed_elsewhere, note
from workspace import Workspace

FOLDER = "relatives"
PREFIX = "memory-"


def command_remember(args) -> int:
    space = Workspace(args.workspace or where.campaign())
    recorded = backlog_of(space)
    if not recorded:
        raise SystemExit("this workspace has no init event; run `init` first")
    root = pathlib.Path(recorded)
    if not root.is_dir():
        print(f"{root} is one file, not a tree of molecules: a memory relative lives "
              "in a molecule's own relatives/ folder, and this backlog has none")
        return 0
    counts = write_memory(root, space.events())
    left = f", {counts['left_alone']} left alone (not text)" if counts["left_alone"] else ""
    print(f"remember: {counts['written']} memory notes written, "
          f"{counts['unchanged']} already saying it{left}, under {root}")
    for name, aimed in sorted(counts["aimed_at"].items()):
        print(f"  {name}: its front matter points at {aimed}, not at this card — left as "
              "it is, so whoever aimed it there decides")
    print(f"  from {counts['events']} events — {counts['no_section']} of a kind this "
          f"note has no section for, {counts['not_a_card']} sections about a node the "
          f"backlog does not hold, {counts['unreadable']} it could not read")
    return 0


def write_memory(root: pathlib.Path, rows: list) -> dict:
    """Refresh every card's memory from these events, and say what happened.

    The write is skipped when the bytes are the same, so a second run leaves
    every mtime where it was — `backlog_tree._one` earns its keep the same way.
    """
    memory, counts = dated(rows)
    paths = backlog_tree.read(root)[backlog_tree.PATHS]
    link = cardfile.linker(root)
    counts.update(written=0, unchanged=0, left_alone=0, aimed_elsewhere=0, aimed_at={},
                  events=len(rows),
                  not_a_card=sum(len(sections) for node, sections in memory.items()
                                 if node not in paths))
    for task_id, card in sorted(paths.items()):
        target = card.parent / FOLDER / f"{PREFIX}{card.stem}{cardfile.SUFFIX}"
        raw = target.read_bytes() if target.exists() else b""
        try:
            was = raw.decode("utf-8")
        except UnicodeDecodeError:
            # Not text this can read, so it cannot say which sections are a
            # person's: leaving the file exactly as it is, is the only answer
            # that cannot lose what somebody put there.
            counts["left_alone"] += 1
            continue
        aimed = aimed_elsewhere(was, link(task_id))
        if aimed:
            counts["aimed_elsewhere"] += 1
            counts["aimed_at"][task_id] = aimed
        text = note(link(task_id), memory.get(task_id) or [], was)
        if raw == text.encode("utf-8"):
            counts["unchanged"] += 1
            continue
        durable.replace(target, text)
        counts["written"] += 1
    return counts
