"""The question a contract reviewer is asked about each file the card uses.

`contract_prompt` already carried the rule — refuse a card whose files do not
cover what its gate can fail on — and the rule works: one card was refused
before any builder started because the reviewer reasoned that the method it
used throws on the case the gate asserts, and the card did not grant that file.
Its sibling in the same molecule was the same shape, was accepted, and its
builder spent a full build before the file fence stopped it (2026-09-18).

So the check was unreliable, not missing. What made the branch reviewer
reliable in that same campaign was being made to take the items ONE AT A TIME
by name rather than reading a general clause, and that is all this is: the
card's own used files, listed, with the question put about each.

Only files the card does NOT grant are listed. A granted file is already
covered, and asking about it would teach the reviewer to refuse cards that are
right.
"""

from __future__ import annotations

from molecule import split


def ungranted(task: dict) -> list[str]:
    """The files this card uses and does not grant, first mention first."""
    granted, found = set(task.get("files") or []), []
    for name in task.get("uses") or []:
        try:
            path, _text = split(name)
        except ValueError:      # not a name; `available` refuses it at planning
            continue
        if path not in granted and path not in found:
            found.append(path)
    return found


def question(task: dict) -> str:
    """One paragraph, or nothing when the card uses only what it grants."""
    files = ungranted(task)
    if not files:
        return ""
    return (
        "\nThis card uses files it does not grant. Take them one at a time, and for "
        "each one answer in your own head: as the repository stands today, is the "
        "gate red because of what is in THIS file? If it is, the builder cannot "
        "make the gate pass without editing it, the file fence will stop it, and "
        "the card is impossible as written — refuse it and say which file it must "
        "grant, or that the work in it belongs to an earlier card. If the gate is "
        "red only because the card's own granted files are missing or incomplete, "
        "that is fine.\n" + "".join(f"  - {path}\n" for path in files))
