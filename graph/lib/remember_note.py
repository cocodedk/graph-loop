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

The place a kept section comes back to is its index among the sections after
`## Node`. That holds because the log only ever grows at the END: a note
written after the third thing that happened is still after the third thing next
week, however much has happened since.
"""

from __future__ import annotations

import re

import cardfile
import yaml  # type: ignore[import-untyped]  # no stubs in this environment

MARK = " — from the log"
NODE = "Node"
HEADING = re.compile(r"(?m)^## +(?P<heading>.+?)[ \t]*$")


def note(target: str, written: list, was: str = "") -> str:
    """This node's memory as it should stand.

    `target` is the link the vault resolves (`T26/02-schema`), `written` is
    what the log says as (heading, body) pairs in the order it happened, and
    `was` is whatever the file holds today — empty for a note being made.
    """
    front = yaml.safe_dump({"kind": "memory", "node": f"[[{target}]]"},
                           sort_keys=False, allow_unicode=True).rstrip()
    fresh = [f"## {heading}{MARK}\n\n{body}" for heading, body in written]
    for where, kept in _theirs(was):
        fresh.insert(min(where, len(fresh)), kept)
    return "\n\n".join([f"---\n{front}\n---", f"## {NODE}\n\n- [[{target}]]", *fresh]) + "\n"


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
