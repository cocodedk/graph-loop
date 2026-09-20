"""The bytes of one memory relative, from what the log says and what a person
added.

A relative has a card's shape — front matter, then `## ` sections — so the loop
can read it later without learning a second format (docs/RELATIVES.md).

**The command owns two things in this file and nothing else.** The sections
whose heading ends with `MARK`, and `kind` / `node` in the front matter while
the note carries neither (`remember_front.py`). Everything else is the
person's and comes back byte for byte: the text before the first heading,
whatever they put under `## Node` besides the link line, and every unmarked
section. A person who ends their own heading with `MARK` is claiming the
command's name for it, and the next run takes that section over — which is the
one thing somebody writing here has to know, and it is in the docs.

The place a kept section comes back to is its index among the sections. That
holds because the log only ever grows at the END: a note written after the
third thing that happened is still after the third thing next week, however
much has happened since.
"""

from __future__ import annotations

import re

import cardfile
import remember_front

MARK = " — from the log"
NODE = "Node"
HEADING = re.compile(r"(?m)^## +(?P<heading>.+?)[ \t]*$")


def refresh(target: str, written: list, was: str = "") -> tuple[str | None, str]:
    """This node's memory as it should stand, and what could not be done to it.

    `target` is the link the vault resolves (`T26/02-schema`), `written` is what
    the log says as (heading, body) pairs in the order it happened, and `was` is
    whatever the file holds today — empty for a note being made. A text of None
    says this file is not the command's to write at all.
    """
    aimed = remember_front.aimed_elsewhere(was, target)
    if aimed:
        return None, (f"its front matter points at {aimed}, not at this card, so "
                      "nothing here was changed")
    front, concern = remember_front.block(was, target)
    found = cardfile.FRONT.match(was)
    fresh = [f"## {heading}{MARK}\n\n{said}" for heading, said in written]
    before, kept = _theirs(found["body"] if found else was)
    for where, text in kept:
        fresh.insert(min(where, len(fresh)), text)
    fresh = _with_node(fresh, target)
    return "\n\n".join([front, *([before] if before else []), *fresh]) + "\n", concern


def _theirs(body: str) -> tuple[str, list[tuple[int, str]]]:
    """What this note holds that the command did not write: the text before the
    first heading, and every unmarked section with where it sat.

    Their own bytes to the last character: only the blank lines BETWEEN pieces
    belong to this file, so a piece is taken with its trailing newlines stripped
    and put back with the one separator every piece gets. Without that, a
    section that moves from the end of the file to the middle grows a blank
    line on every run and the note is never twice the same.
    """
    marks = list(HEADING.finditer(body))
    before = body[:marks[0].start() if marks else len(body)].strip("\n")
    kept: list[tuple[int, str]] = []
    for order, mark in enumerate(marks):
        stop = marks[order + 1].start() if order + 1 < len(marks) else len(body)
        if not mark["heading"].rstrip().endswith(MARK):   # a note from Windows carries \r
            kept.append((order, body[mark.start():stop].rstrip("\n")))
    return before, kept


def _with_node(sections: list[str], target: str) -> list[str]:
    """The one guarantee the command makes about `## Node`: it is there, and
    the link is in it. A section a person already wrote under that heading is
    theirs — the link is put in when it is missing, and nothing else in it is
    moved, rewritten or taken out."""
    where = next((order for order, text in enumerate(sections)
                  if _heading(text) == NODE), None)
    if where is None:
        return [f"## {NODE}\n\n- [[{target}]]", *sections]
    line = f"- [[{target}]]"
    theirs = sections[where]
    if any(row.strip() == line for row in theirs.splitlines()):
        return sections
    heading, _, rest = theirs.partition("\n")
    return [*sections[:where], f"{heading}\n\n{line}\n{rest}".rstrip("\n"),
            *sections[where + 1:]]


def _heading(section: str) -> str:
    found = HEADING.match(section)
    return found["heading"].rstrip() if found else ""
