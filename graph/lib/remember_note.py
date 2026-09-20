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

import remember_front
import remember_read

MARK = " — from the log"
NODE = "Node"
# Up to three spaces before the hashes, as CommonMark has it. A heading missed
# for its indentation was swallowed by the generated section above it and
# deleted with it (an independent review).
HEADING = re.compile(r"^ {0,3}## +(?P<heading>.+?)[ \t]*$")


def refresh(target: str, written: list, was: str = "") -> tuple[str | None, str]:
    """This node's memory as it should stand, and what could not be done to it.

    `target` is the link the vault resolves (`T26/02-schema`), `written` is what
    the log says as (heading, body) pairs in the order it happened, and `was` is
    whatever the file holds today — empty for a note being made. A text of None
    says this file is not the command's to write at all.
    """
    if not was:                       # a note the command is making: its own from end to end
        return _put(remember_front.fresh(target), "", [], target, written), ""
    mine, why = remember_front.ours(was, target)
    if not mine:                      # the one door: nothing else decides this
        return None, why
    block, body = remember_read.split(was)
    before, kept = _theirs(body)
    return _put(block, before, kept, target, written), remember_front.missing(was)


def _put(block: str, before: str, kept: list, target: str, written: list = ()) -> str:
    """The note, assembled from the pieces that were already there and the
    sections the command owns. `block` is the front matter's own bytes — never
    rebuilt, because rebuilding it dropped a delimiter's spacing once."""
    fresh = [f"## {heading}{MARK}\n\n{said}" for heading, said in written]
    for where, text in kept:
        fresh.insert(min(where, len(fresh)), text)
    fresh = _with_node(fresh, target)
    return block.rstrip("\n") + "\n\n" + "\n\n".join(
        [*([before] if before else []), *fresh]) + "\n"


def _theirs(body: str) -> tuple[str, list[tuple[int, str]]]:
    """What this note holds that the command did not write: the text before the
    first heading, and every unmarked section with where it sat.

    Their own bytes to the last character: only the blank lines BETWEEN pieces
    belong to this file, so a piece is taken with its trailing newlines stripped
    and put back with the one separator every piece gets. Without that, a
    section that moves from the end of the file to the middle grows a blank
    line on every run and the note is never twice the same.
    """
    marks = _headings(body)
    before = body[:marks[0][0] if marks else len(body)].strip("\n")
    kept: list[tuple[int, str]] = []
    for order, (at, heading) in enumerate(marks):
        stop = marks[order + 1][0] if order + 1 < len(marks) else len(body)
        if not heading.endswith(MARK):
            kept.append((order, body[at:stop].rstrip("\n")))
    return before, kept


def _headings(text: str) -> list[tuple[int, str]]:
    """Every real `## ` heading, as (where it starts, what it says). Asked of
    `remember_read.plain`, the one scanner that knows where code is."""
    found = []
    for at, line in remember_read.plain(text)[0]:
        head = HEADING.match(line)
        if head:
            found.append((at, head["heading"]))
    return found


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
    if any(row.strip() == line for _, row in remember_read.plain(theirs)[0]):
        return sections
    heading, _, rest = theirs.partition("\n")
    return [*sections[:where], f"{heading}\n\n{line}\n{rest}".rstrip("\n"),
            *sections[where + 1:]]


def _heading(section: str) -> str:
    """A section's own heading — its first line, never a line further down."""
    found = HEADING.match(section.split("\n", 1)[0])
    return found["heading"] if found else ""
