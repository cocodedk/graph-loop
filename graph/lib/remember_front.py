"""Whose memory note this is, and the front matter of one the command makes.

**Front matter that is already there is never edited. At all.** Not a line
added, not a key completed. YAML has more valid spellings than a text edit can
know about — flow mappings, blocks indented two spaces, an explicit `...`
terminator, anchors, comments — and three attempts to add a missing key safely
each broke a valid note in front of a reviewer. Reading it into a mapping and
writing it back is no better: it loses the order, the quoting and the comments
somebody chose. So only a note the command MAKES gets front matter written.

**Whose note it is, is asked once, here, and conservatively.** No `node` at all
means it is this card's by where it sits. A `node` that is a string and exactly
this card's link means the same. Anything else is somebody else's: another
card's link, a list holding one, a number, front matter that will not parse.
The list is the one that mattered — a guard that only looked at strings let it
through and a foreign note's history was rebuilt under a foreign link.

The parser raises more than `YAMLError`: `node: 2026-99-99` reaches the date
constructor and raises `ValueError`, `!!int nonsense` the int constructor. Every
one of them means the same thing here, so every one of them is caught.
"""

from __future__ import annotations

import remember_read
import yaml  # type: ignore[import-untyped]  # no stubs in this environment

KIND = "memory"
OWNED = ("kind", "node")


def ours(text: str, target: str) -> tuple[bool, str]:
    """Whether this note is this card's to refresh, and why not.

    The only door: nothing else in the command decides whether to write a note.
    `text` has already been through `remember_read.understood`, so it has front
    matter; a file that has none never reaches here and is never written.
    """
    holds = _holds(remember_read.front(text))
    if holds is None:
        return False, ("its front matter will not read as a mapping, so nothing here "
                       "can say which card it is about; nothing here was changed")
    if "node" not in holds:
        return True, ""                      # unclaimed: this card's by where it sits
    aimed = holds["node"]
    if isinstance(aimed, str) and aimed == f"[[{target}]]":
        return True, ""
    return False, (f"its front matter names {str(aimed)[:80]} as its node, not this "
                   "card; nothing here was changed")


def missing(text: str) -> str:
    """What this note's front matter does not carry, said rather than added."""
    holds = _holds(remember_read.front(text)) or {}
    absent = [key for key in OWNED if key not in holds]
    return "" if not absent else (
        f"its front matter carries no {' and no '.join(absent)}, and front matter "
        "that is already there is never edited, so nothing was added")


def fresh(target: str) -> str:
    """The front-matter block for a note the command is making. The only one
    it ever writes."""
    return "---\n" + yaml.safe_dump(
        {"kind": KIND, "node": f"[[{target}]]"},
        sort_keys=False, allow_unicode=True).rstrip() + "\n---\n"


def _holds(front: str) -> dict | None:
    """This front matter as a mapping, or None when it is not one — a list, a
    scalar, several documents in one, a value whose tag will not construct, or
    text somebody broke while editing. Read only; nothing is written back."""
    try:
        holds = yaml.safe_load(front)
    except Exception:  # noqa: BLE001 — every way it can fail means the same thing here
        return None
    if holds is None:
        return {}
    return holds if isinstance(holds, dict) else None
