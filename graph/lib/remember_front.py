"""A memory note's front matter: the person's, with two keys added if absent.

It is kept as TEXT and never read into a mapping and written back out — that
reorders the keys, requotes the values and drops the comments, and a vault that
carries a property set on every note and queries it across the vault would lose
that set every time the command ran.

Only `kind` and `node` are this command's, and only while the note carries
neither. A key that is there stands, whatever it says, and a `node` aimed at
another note means the whole file is somebody else's business.
"""

from __future__ import annotations

import cardfile
import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from front_matter import entry

KIND = "memory"


def block(was: str, target: str) -> tuple[str, str]:
    """The front-matter block this note should carry, and what could not be
    done to it. The concern is empty when there was nothing to say."""
    found = cardfile.FRONT.match(was)
    if not found:
        return "---\n" + yaml.safe_dump(
            {"kind": KIND, "node": f"[[{target}]]"},
            sort_keys=False, allow_unicode=True).rstrip() + "\n---", ""
    front = found["front"]
    kept = f"---\n{front}\n---"
    if not front.strip():
        return _added("", target), ""      # nothing there: the two lines are the whole of it
    holds = _mapping(front)
    if holds is None:
        return kept, ("its front matter is not a mapping this can read, so kind and "
                      "node were left out of it")
    missing = [key for key, _ in _wanted(target) if entry(front, key) is None]
    if not missing:
        return kept, ""
    if holds.flow_style:
        # `{kind: memory}` holds its keys inside the braces. A line put after
        # the closing one is not in the mapping — it is not even YAML, and the
        # note would stop parsing for everyone, this command included.
        return kept, (f"its front matter is written in flow style, where {_and(missing)} "
                      "cannot be added as a line, so it was left out")
    return _added(front, target), ""


def aimed_elsewhere(was: str, target: str) -> str:
    """The node this file already points at, when that is not `target`.

    A person may have aimed it at a note that was since renamed. The command
    then writes NOTHING here: rebuilding the history of a note that says it is
    about another card is the one mistake no counter makes up for.
    """
    found = cardfile.FRONT.match(was)
    try:
        holds = yaml.safe_load(found["front"]) if found else None
    except yaml.YAMLError:
        return ""
    aimed = holds.get("node") if isinstance(holds, dict) else None
    return "" if not isinstance(aimed, str) or aimed == f"[[{target}]]" else aimed


def _added(front: str, target: str) -> str:
    """The front matter with each missing key put in as one line, through
    `cardfile.patch` — the one writer here that adds a front-matter line and
    leaves every other byte of the note where it was."""
    text = f"---\n{front}\n---\n"
    for key, value in _wanted(target):
        if entry(cardfile.FRONT.match(text)["front"], key) is None:
            text = cardfile.patch(text, key, value)
    return text.rstrip("\n")


def _wanted(target: str) -> tuple[tuple[str, str], ...]:
    return ("kind", KIND), ("node", f"[[{target}]]")


def _mapping(front: str):
    """This front matter as a YAML mapping node, or None when it is not one —
    a list, a scalar, or text somebody broke while editing it. Composed, not
    loaded: `flow_style` is the thing being asked about, and only the node
    carries it."""
    try:
        holds = yaml.compose(front)
    except yaml.YAMLError:
        return None
    return holds if isinstance(holds, yaml.MappingNode) else None


def _and(missing: list) -> str:
    return " and ".join(missing)
