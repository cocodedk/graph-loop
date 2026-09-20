"""Whether one memory note may be written, and whether it still may.

Split out of `remember.py` at the 200-line cap. Two questions, and neither
answers the other. Where does the path REALLY lead — asked of the filesystem,
of every ancestor at once. And are the bytes at the end of it still the ones
the ownership check looked at a moment ago.
"""

from __future__ import annotations

import pathlib


def still(note: pathlib.Path, raw: bytes | None) -> bool:
    """Whether the file is still what the ownership check above saw: the same
    bytes, or still not there at all."""
    return (note.read_bytes() if note.exists() else None) == raw


def unsafe(inside: pathlib.Path, done: set, card: pathlib.Path,
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
