"""The law a sliced card must obey: never name what does not exist yet.

Four times in one week a card named something the product does not have — a
model `gpt-5.6`, an event `OBSERVATION_RECORDED` used as a verdict, a durable
field `outcome_facts`, an `observation` field on the story — and each cost the
loop a day of refusals. The mistake is always the same shape, so the check is
one rule:

    every name an atom uses must already exist, or an earlier atom in the
    same molecule must say it creates it.

A name is written `path:text` — the file that must contain it, and the text
that must be in that file. Existence is asked of the repository, never of a
list kept beside it, because a hand-written list of what is present drifts
from the thing it describes.
"""

from __future__ import annotations

import pathlib
import re

import cardfile

NAME = re.compile(r"^(?P<path>[^\s:]+):(?P<text>.+)$")
NUMBERED = re.compile(r"^(?P<order>\d+)-(?P<stem>.+)\.md$")   # `cardfile.SUFFIX`


def split(name: str) -> tuple[str, str]:
    """`path:text` as its two halves. Anything else is not a name."""
    found = NAME.match(name.strip())
    if not found:
        raise ValueError(
            f"{name!r} is not a name: write it as path:text, the file that must "
            "hold it and the text that must be in that file")
    return found["path"], found["text"]


def present(root: pathlib.Path):
    """Ask the repository whether a name is there. Reads each file once.

    A name outside the repository is no name at all: `/etc/passwd:root` and
    `../other/app.py:x` would otherwise let a card prove itself against
    something the card can never change.
    """
    base = root.resolve()
    seen: dict[str, str | None] = {}

    def look(name: str) -> bool:
        path, text = split(name)
        if path not in seen:
            whole = (base / path).resolve()
            try:
                whole.relative_to(base)
                seen[path] = whole.read_text("utf-8", errors="replace")
            except (OSError, ValueError):    # no such file, or not in the repository
                seen[path] = None
        body = seen[path]
        return body is not None and text in body

    return look


def unavailable(atoms: list[dict], look) -> list[tuple[str, str]]:
    """Every (atom id, name) the atom uses that nothing has made yet.

    `look` answers for the repository as it stands; `creates` answers for the
    atoms ahead of this one. An atom may use what it creates itself: the card
    that writes a field also reads it back in its own gate.
    """
    made: set[str] = set()
    missing = []
    for atom in atoms:
        # A `creates` that is not a name licenses nothing — otherwise the same
        # malformed text on both sides would pass itself.
        for name in atom.get("creates") or []:
            split(name)
            made.add(name)
        for name in atom.get("uses") or []:
            if name not in made and not look(name):
                missing.append((str(atom.get("id") or "?"), name))
    return missing


def ordered(folder: pathlib.Path) -> list[pathlib.Path]:
    """The molecule's atoms, in the one order it declares: the file names.

    The number in front of each file IS the order, so there is nothing to keep
    in step with it. A file without one is not an atom and stops the read,
    because a molecule that half-declares its order builds half a piece. It is
    read as a number, not as text: sorted as text, `100-b` comes before `99-a`
    and every wait inside the molecule is derived backwards.
    """
    atoms: list[pathlib.Path] = []
    stray: list[pathlib.Path] = []
    for path in sorted(folder.iterdir()):
        if path.name == cardfile.HEAD or path.is_dir() or path.suffix != cardfile.SUFFIX:
            continue
        found = NUMBERED.match(path.name)
        (atoms if found else stray).append(path)
    if stray:
        raise ValueError(
            f"{folder.name} holds {', '.join(p.name for p in stray)}, which carry no "
            "order: an atom is named NN-stem.md and the number is the order")
    return sorted(atoms, key=lambda path: (stage(path.name), path.name))


def atom_id(folder_name: str, file_name: str) -> str:
    """An atom's id, derived from where it sits — never stored a second time."""
    found = NUMBERED.match(file_name)
    if not found:
        raise ValueError(f"{file_name} is not an atom: it is named NN-stem.md")
    return f"{folder_name}.{found['stem']}"


def stage(file_name: str) -> int:
    """An atom's number: everything with a lower one comes first, and two atoms
    sharing one run side by side."""
    found = NUMBERED.match(file_name)
    if not found:
        raise ValueError(f"{file_name} is not an atom: it is named NN-stem.md")
    return int(found["order"])


def unknown_names(task: dict, rows: list[dict], root: pathlib.Path) -> str:
    """Why this card may not start, or "" when every name it uses is there.

    What the cards it waits for say they create counts as there: that is what
    makes an order mean something. Asked before a builder is paid, so a card
    that names a field nothing emits is refused for nothing.
    """
    if not (task.get("uses") or []):
        return ""
    waits = set(task.get("needs") or [])
    ahead = [row for row in rows if row.get("id") in waits]
    try:
        missing = [name for who, name in unavailable([*ahead, task], present(root))
                   if who == task.get("id")]
    except ValueError as badly_written:
        # A card written wrong is a card to rewrite, not a lane that crashed.
        return str(badly_written)
    if not missing:
        return ""
    return ("this card uses names that are not there and nothing it waits for makes "
            f"them: {', '.join(missing)}. Either the card that makes each one comes "
            "first, or the name is wrong")
