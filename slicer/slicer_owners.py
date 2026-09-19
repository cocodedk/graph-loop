"""One law, split from `slicer_law` at the 200-line cap: who owns a file.

`slicer_law` stays the door — it re-exports `assert_one_owner`, and every
caller keeps importing it from there.
"""

from __future__ import annotations

import pathlib
import sys

from slicer_graph import _graph, _ordered

DRIVE_LIB = pathlib.Path(__file__).resolve().parents[1] / "drive" / "lib"
sys.path.insert(0, str(DRIVE_LIB))
from backlog_status import DONE, DROPPED  # type: ignore[import-not-found]


def assert_one_owner(name: str, made: dict, rows: list[dict], target: dict | None) -> None:
    """No two cards that can run at the same time grant the same file.

    A card's files are its write authority, and a builder gets a private
    worktree. Two unordered cards holding the same file are two builders
    editing it apart from each other: whichever commits second clobbers the
    first or fails its gate on a file that moved under it. Ordered cards are
    safe and ordinary — a molecule's own stage 2 shares files with its stage 1,
    and is cut from the tree after stage 1 landed — so the law is ordering, not
    exclusivity.

    It is asked of the whole prospective graph, so it also closes the one input
    that defeats the plan phase's exhaustion rule. Only "its name is new" was
    enforced, and a rename satisfies that for free, so a planner re-planning
    covered work under a new name published a real change every round and the
    phase had no reason to stop (2026-09-18, killed by hand at 17 tasks). The
    same composition grants the same files, so this refuses it — and says what
    to answer instead, because a planner shown only a rule invents a way past
    it.

    Three kinds of card own nothing. A settled one: its work is committed, and
    a later card granting the same file is building on landed code rather than
    racing. The target: it is the card being replaced, and it hands its files
    down. And a card that has already been sliced, because its work belongs to
    its children now and no builder will ever be offered it — read from the
    record (another row names it in `sliced_from`) rather than from its status
    word, the same reason every other inventory here is.
    """
    graph, ids = _graph(name, made, rows, target)
    mine, spent = dict(zip(ids, made.get("atoms") or [])), DONE + DROPPED
    if not ids:
        mine = {name: made}
    sliced = {str(row["sliced_from"]) for row in rows if row.get("sliced_from")}
    if target:
        sliced.add(str(target.get("id")))
    held: dict[str, str] = {}
    for row in rows:
        if str(row.get("status")) in spent or str(row.get("id")) in sliced:
            continue
        for path in row.get("files") or []:
            held.setdefault(str(path), str(row.get("id")))
    for claimed, leaf in mine.items():
        for path in leaf.get("files") or []:
            owner = held.get(str(path))
            if owner and not _ordered(graph, claimed, owner):
                raise ValueError(
                    f"{owner} already holds {path}, and {claimed} would hold it too with "
                    f"nothing ordering them: two builders would write that file apart from "
                    f"each other. If this work is {owner}'s work, answer NO_GAP — it is "
                    f"already planned. If it genuinely comes after it, say so in needs.")
