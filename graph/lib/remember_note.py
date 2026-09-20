"""The bytes of one memory relative, from what the log says and what a person
added.

A relative has a card's shape — front matter, then `## ` sections — so the loop
can read it later without learning a second format (docs/DESIGN.md, "Relatives:
memory and learning around a card").

Two hands write in this file, and one rule tells them apart: **every heading
this command writes ends with `MARK`.** Any other `## ` section is a person's,
and comes back byte for byte, at the place in the file they put it. A person
who ends their own heading with `MARK` is claiming the command's name for it,
and the next run takes that section over — which is the one thing somebody
writing here has to know, and it is in the docs.

The front matter is nobody's but the person's. It is kept as TEXT — never read
into a mapping and written back out, which reorders keys, requotes values and
drops comments — and only a missing `kind` or `node` is added. A vault that
carries a property set on every note and queries it across the vault would
otherwise lose that set each time this command ran. A `node` that points at
another note is a decision somebody made, perhaps after a rename: it is counted
and said out loud, never written over.

The place a kept section comes back to is its index among the sections after
`## Node`. That holds because the log only ever grows at the END: a note
written after the third thing that happened is still after the third thing next
week, however much has happened since.
"""

from __future__ import annotations

import re

import cardfile
import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from front_matter import entry

MARK = " — from the log"
NODE = "Node"
KIND = "memory"
HEADING = re.compile(r"(?m)^## +(?P<heading>.+?)[ \t]*$")


def note(target: str, written: list, was: str = "") -> str:
    """This node's memory as it should stand.

    `target` is the link the vault resolves (`T26/02-schema`), `written` is
    what the log says as (heading, body) pairs in the order it happened, and
    `was` is whatever the file holds today — empty for a note being made.
    """
    fresh = [f"## {heading}{MARK}\n\n{body}" for heading, body in written]
    for where, kept in _theirs(was):
        fresh.insert(min(where, len(fresh)), kept)
    return "\n\n".join([_front(was, target), f"## {NODE}\n\n- [[{target}]]", *fresh]) + "\n"


def _front(was: str, target: str) -> str:
    """The note's front matter block, `---` lines and all.

    A note that has one keeps its own text exactly: this never parses it into
    a mapping and dumps it back, because that reorders the keys, requotes the
    values and throws the comments away. A key that is missing is added
    through `cardfile.patch`, the one writer in this repository that puts a
    line into front matter and leaves every other byte where it was. A key
    that is THERE is left as it stands, whatever it says.
    """
    found = cardfile.FRONT.match(was)
    if not found:
        return "---\n" + yaml.safe_dump({"kind": KIND, "node": f"[[{target}]]"},
                                        sort_keys=False, allow_unicode=True).rstrip() + "\n---"
    block = f"---\n{found['front']}\n---\n"
    for key, value in (("kind", KIND), ("node", f"[[{target}]]")):
        if _missing(found["front"], key):
            block = cardfile.patch(block, key, value)
    return block.rstrip("\n")


def _missing(front: str, key: str) -> bool:
    """Whether the front matter has no entry for this key. Front matter a
    person broke while editing answers "no": adding a line to something that
    will not parse would only make the damage harder to see."""
    try:
        return entry(front, key) is None
    except yaml.YAMLError:
        return False


def aimed_elsewhere(was: str, target: str) -> str:
    """The node this file already points at, when that is not `target`, so the
    command can say so instead of writing over it. Parsed, because a value is
    quoted however the writer felt — a read, never a rewrite."""
    found = cardfile.FRONT.match(was)
    try:
        holds = yaml.safe_load(found["front"]) if found else None
    except yaml.YAMLError:
        return ""
    aimed = holds.get("node") if isinstance(holds, dict) else None
    return "" if not isinstance(aimed, str) or aimed == f"[[{target}]]" else aimed


def _theirs(was: str) -> list[tuple[int, str]]:
    """A person's own sections, and where each one sat.

    Their own bytes to the last character: only the blank lines BETWEEN
    sections belong to this file, so a section is taken with its trailing
    newlines stripped and put back with the same one separator every section
    gets. Without that, a kept section that moves from the end of the file to
    the middle grows a blank line on every run and the note is never twice the
    same.
    """
    found = cardfile.FRONT.match(was)
    body = found["body"] if found else was
    marks = list(HEADING.finditer(body))
    kept: list[tuple[int, str]] = []
    skipped = 0
    for order, mark in enumerate(marks):
        stop = marks[order + 1].start() if order + 1 < len(marks) else len(body)
        heading = mark["heading"].rstrip()     # a note written on Windows carries \r
        if not order and heading == NODE:
            skipped = 1
        elif not heading.endswith(MARK):
            kept.append((order - skipped, body[mark.start():stop].rstrip("\n")))
    return kept
