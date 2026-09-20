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

A `## ` line inside a fenced code block is an example, not a heading — not for
ownership, not for splitting sections, not for finding the link under
`## Node`. Without that, a person showing what a generated section looks like
had their example read as the command's own and lost it, with everything after
it (an independent review). An INDENTED code block needs no rule of its own: a
heading is a `## ` at column zero and every line of an indented block carries
at least four spaces.
"""

from __future__ import annotations

import re

import cardfile
import remember_front

MARK = " — from the log"
NODE = "Node"
HEADING = re.compile(r"^## +(?P<heading>.+?)[ \t]*$")
FENCE = re.compile(r"^ {0,3}(?P<mark>`{3,}|~{3,})(?P<info>.*)$")


def refresh(target: str, written: list, was: str = "") -> tuple[str | None, str]:
    """This node's memory as it should stand, and what could not be done to it.

    `target` is the link the vault resolves (`T26/02-schema`), `written` is what
    the log says as (heading, body) pairs in the order it happened, and `was` is
    whatever the file holds today — empty for a note being made. A text of None
    says this file is not the command's to write at all.
    """
    mine, why = remember_front.ours(was, target)
    if not mine:                      # the one door: nothing else decides this
        return None, why
    found = cardfile.FRONT.match(was)
    before, kept, unclosed = _theirs(found["body"] if found else was)
    if unclosed:
        # No telling where their text ends: every section after the fence would
        # be swallowed into it and written again from the log, and the note
        # would grow by one copy on every run.
        return None, ("it has a fenced block nobody closed, so where a person's own "
                      "text ends cannot be read; nothing here was changed")
    front, concern = remember_front.block(was, target)
    fresh = [f"## {heading}{MARK}\n\n{said}" for heading, said in written]
    for where, text in kept:
        fresh.insert(min(where, len(fresh)), text)
    fresh = _with_node(fresh, target)
    return "\n\n".join([front, *([before] if before else []), *fresh]) + "\n", concern


def _theirs(body: str) -> tuple[str, list[tuple[int, str]], bool]:
    """What this note holds that the command did not write: the text before the
    first heading, and every unmarked section with where it sat — and whether a
    fence was left open, which makes the answer unreadable.

    Their own bytes to the last character: only the blank lines BETWEEN pieces
    belong to this file, so a piece is taken with its trailing newlines stripped
    and put back with the one separator every piece gets. Without that, a
    section that moves from the end of the file to the middle grows a blank
    line on every run and the note is never twice the same.
    """
    marks, unclosed = _headings(body)
    before = body[:marks[0][0] if marks else len(body)].strip("\n")
    kept: list[tuple[int, str]] = []
    for order, (at, heading) in enumerate(marks):
        stop = marks[order + 1][0] if order + 1 < len(marks) else len(body)
        if not heading.endswith(MARK):
            kept.append((order, body[at:stop].rstrip("\n")))
    return before, kept, unclosed


def _headings(text: str) -> tuple[list[tuple[int, str]], bool]:
    """Every real `## ` heading, as (where it starts, what it says), and
    whether a fenced block was left open at the end."""
    found = []
    plain, unclosed = _plain(text)
    for at, line in plain:
        head = HEADING.match(line)
        if head:
            found.append((at, head["heading"].rstrip()))   # a note from Windows carries \r
    return found, unclosed


def _plain(text: str) -> tuple[list[tuple[int, str]], bool]:
    """Every line that is not inside a fenced code block, with where it starts.

    A fence is ``` or ~~~, three or more, indented up to three spaces, with or
    without an info string; it closes on the same character, at least as long,
    with nothing after it. The fence lines themselves are code's, not text's.
    """
    lines: list[tuple[int, str]] = []
    fence = ""
    at = 0
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        opened = FENCE.match(bare)
        if fence:
            if (opened and opened["mark"][0] == fence[0]
                    and len(opened["mark"]) >= len(fence) and not opened["info"].strip()):
                fence = ""
        elif opened:
            fence = opened["mark"]
        else:
            lines.append((at, bare))
        at += len(line)
    return lines, bool(fence)


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
    # Asked of real lines only: a link SHOWN in a fenced example is not the
    # link, and taking it for one would leave the node with no link at all.
    if any(row.strip() == line for _, row in _plain(theirs)[0]):
        return sections
    heading, _, rest = theirs.partition("\n")
    return [*sections[:where], f"{heading}\n\n{line}\n{rest}".rstrip("\n"),
            *sections[where + 1:]]


def _heading(section: str) -> str:
    """A section's own heading — its first line, never a line further down."""
    found = HEADING.match(section.split("\n", 1)[0].rstrip("\r"))
    return found["heading"].rstrip() if found else ""
