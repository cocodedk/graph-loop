"""Whose memory note this is, and its front matter — which is never edited.

**The command does not edit front matter that is already there. At all.** Not a
line added, not a key completed. YAML has more valid spellings than a text edit
can know about — flow mappings, blocks indented two spaces, an explicit `...`
terminator, anchors, comments — and three separate attempts to add a missing
key safely each broke a valid note in front of a reviewer. Reading it into a
mapping and writing it back is no better: it loses the order, the quoting and
the comments somebody chose. So a note the command MAKES gets `kind` and
`node`; a note that exists keeps its own bytes, and the summary says what is
missing from it.

**Whose note it is, is asked once, here, and conservatively.** No `node` at all
means it is this card's by where it sits. A `node` that is a string and exactly
this card's link means the same. Anything else is somebody else's: another
card's link, a list holding one, a number, front matter that will not parse.
The list is the one that mattered — a guard that only looked at strings let it
through and a foreign note's history was rebuilt under a foreign link.
"""

from __future__ import annotations

import cardfile
import yaml  # type: ignore[import-untyped]  # no stubs in this environment

KIND = "memory"
OWNED = ("kind", "node")


def ours(was: str, target: str) -> tuple[bool, str]:
    """Whether this file is this card's memory to refresh, and why not.

    The only door: nothing else in the command decides whether to write a note.
    """
    found = cardfile.FRONT.match(was)
    if not found:
        return True, ""                      # no front matter: nothing else claims it
    holds = _holds(found["front"])
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


def block(was: str, target: str) -> tuple[str, str]:
    """The front-matter block this note carries, and what is missing from it.

    A note that exists gets its own text back, to the byte. Only a note being
    made gets one written, and only that one is ever this command's to write.
    """
    found = cardfile.FRONT.match(was)
    if not found:
        return "---\n" + yaml.safe_dump(
            {"kind": KIND, "node": f"[[{target}]]"},
            sort_keys=False, allow_unicode=True).rstrip() + "\n---", ""
    holds = _holds(found["front"]) or {}
    missing = [key for key in OWNED if key not in holds]
    return f"---\n{found['front']}\n---", "" if not missing else (
        f"its front matter carries no {' and no '.join(missing)}, and front matter "
        "that is already there is never edited, so nothing was added")


def _holds(front: str) -> dict | None:
    """This front matter as a mapping, or None when it is not one — a list, a
    scalar, several documents in one, or text somebody broke while editing.

    Read only. Nothing is ever written back through this.
    """
    try:
        holds = yaml.safe_load(front)
    except yaml.YAMLError:
        return None
    if holds is None:
        return {}
    return holds if isinstance(holds, dict) else None
