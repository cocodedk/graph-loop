"""What a rewritten contract may not do to the card it rewrites.

A planner reads the answer as a shape; this reads it against the CARD — the
questions only the host can answer, because only the host knows what the card
was granted. Asked twice: at the retry, so the one retry carries the reason
back, and again under the write lock, because the graph a rewrite would join is
made of other cards and those move while a rewrite is decided.

The bans are the card's own authority, and none of them is the model's to widen:
a file grant only narrows and is a list of names, a card that changes code
still changes code, and a LIVE contract — its gate, its helper verbs, the stack it acts on — is the
commander's, the same reason the replan path leaves LIVE cards alone.
"""

from __future__ import annotations

import pathlib

import backlog_tree
from accepted_contract import changed_criteria
from backlog_decision import broken_wait
from backlog_status import is_live


def check_rewrite(card: dict, rows: list[dict], contract: dict,
                  tree: pathlib.Path | None = None) -> str:
    """Why this rewrite may not be applied to this card, or "" when it may.

    `tree` is the backlog folder when the backlog is kept as one (`Backlog.path`
    while `is_tree`), because a tree derives an atom's waits from where its file
    sits and gives them back on the next read: the graph to judge is the one the
    tree would restore, not the one the answer states.
    """
    if is_live(card):
        return ("a LIVE card's contract is the commander's: its gate performs the "
                "work it measures, and a model may not rewrite that")
    granted = [str(name) for name in card.get("files") or []]
    asked = [] if contract.get("files") is None else contract.get("files")
    if not isinstance(asked, list) or not all(
            isinstance(name, str) and name.strip() for name in asked):
        # Read before it is counted: `or []` called every falsy answer an empty
        # grant, so a planner's `files:` (nothing at all) turned a card that
        # changes code into one that changes none, which is finding 7 again.
        return ("a rewrite's file grant is a list of names, and "
                f"{asked!r} is not one")
    if granted and not asked:
        return ("this card changes files; a rewrite may not turn it into a card "
                "with none, which is a card no builder is ever called for: no "
                "builder, no red proof and no diff review")
    widened = sorted(set(asked) - set(granted))
    if widened:
        # An empty grant is still a grant: a card that changes no file may not
        # be handed one. `granted and widened` asked whether the card had files
        # before asking whether the rewrite had added any (Codex, finding 8).
        return ("the rewrite reaches outside the card's files — it may narrow the "
                "grant, never widen it: " + ", ".join(widened)
                + " was not granted to this card")
    fixed = changed_criteria(card, contract)
    if fixed:
        return fixed
    # The graph as it WOULD stand: a rewrite that waits on an id nobody holds,
    # or on itself, is a card that would never be startable again. Asked of the
    # EFFECTIVE waits, because a tree gives derived ones back: `M.b.needs: []`
    # passed here while the next read restored M.b → M.a → X → M.b.
    asked = contract["needs"] if "needs" in contract else list(card.get("needs") or [])
    card_id = str(card.get("id") or "")
    moved = {card_id: list(asked)} if tree is None else \
        backlog_tree.after_write(tree, card_id, asked)
    effective = moved.get(card_id, list(asked))
    if set(effective) != set(asked):
        return ("the tree derives this card's waits from where its file sits, so it "
                "cannot store them as this rewrite states them: the card would wait "
                f"for {', '.join(sorted(map(str, effective))) or 'nothing'}, not "
                f"{', '.join(sorted(map(str, asked))) or 'nothing'}. An atom cannot "
                "drop the atoms it runs behind or the waits its molecule hands it, "
                "and it cannot add one on an atom of its own molecule that runs later")
    return _stranded(card, contract, rows, effective, moved)


def _stranded(card: dict, contract: dict, rows: list[dict], effective: list,
              moved: dict[str, list]) -> str:
    """Which card this rewrite would leave waiting for ever, or "".

    Every card the write re-aims is asked, not the rewritten one alone: the tree
    hands a molecule's waits down to its first stage, so `M.needs = [X, M.a]` is
    a fine graph where M sits and closes M.a → X → M.a one level down (Codex on
    028ecb63).
    """
    card_id = str(card.get("id") or "")
    changed = {card_id: {**card, **contract, "needs": effective, "status": "todo"}}
    for row in rows:
        other = str(row.get("id") or "")
        if other != card_id and other in moved \
                and set(moved[other]) != set(row.get("needs") or []):
            changed[other] = {**row, "needs": moved[other]}
    ahead = [changed.get(str(row.get("id") or ""), row) for row in rows]
    for other, row in changed.items():
        broken = broken_wait(row, ahead)
        if broken:
            return f"the rewritten card would never start: {broken}" if other == card_id \
                else (f"the rewrite re-aims {other}, which the tree derives from this "
                      f"card's file, and then it would never start: {broken}")
    return ""
