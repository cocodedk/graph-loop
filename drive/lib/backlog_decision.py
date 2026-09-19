"""Who may take a card the loop is not building, and why one can never end.

One predicate each, so the scheduler, the board, the doctor and the tests cannot
disagree. `Backlog.ready()` is not the same question — it deliberately keeps
held cards — and absence from `startable()` is not either, because a card whose
files another lane holds for an hour is not abandoned.

There is no decider any more: a card no actor will take is not asked about, it
ends the campaign with its gap named (`finishing`). Nothing here calls a model.
"""

from __future__ import annotations

from backlog_status import is_live, settled
from replan import MAX_REPLANS


def can_replan(card: dict) -> bool:
    """Whether `turn.replan_pending` takes this card: a refused contract with
    replans left, unheld, and not LIVE.

    A hold is a decision about the card, and a LIVE contract's gate, verbs,
    files and wording are the commander's: a planner's rewrite of them stranded
    T2 three times (files dropped, anchors the gate never had), so a refused
    live contract is not the planner's to rewrite.
    """
    return bool(card.get("status") == "refused_contract"
                and int(card.get("replans") or 0) < MAX_REPLANS
                and not card.get("blocked_by_human") and not is_live(card))


def broken_wait(card: dict, rows: list[dict]) -> str:
    """Why THIS card's own dependencies can never resolve, or "".

    A need the backlog does not hold, a `sliced` parent cut into no pieces, or a
    card its own needs lead back to: none of those ends by waiting, and waiting
    on them is how a card hides for ever.

    Only the card's own defect is named. A healthy card waiting behind a broken
    one keeps waiting: sweeping the dependants in too would send a whole branch
    of the backlog out of the queue for one bad id, and the cards actually in the
    cycle — each of which reaches itself — are decided anyway.

    A need that has SETTLED ends the wait, so the walk stops there: what a
    finished card names in its own needs is history, and following it found a
    card in its own closure and called a runnable card a ring (Codex, finding
    1 — `done` and `dropped` both settle, and both did it).
    """
    by_id = {row.get("id"): row for row in rows}
    for need in card.get("needs") or []:
        if need not in by_id:
            return f"it waits on {need}, which the backlog does not hold"
    if card.get("status") == "sliced" and not (card.get("needs") or []):
        return "it was sliced into no pieces, so nothing carries its work"
    finished = settled(rows or [card])
    seen: set = set()
    walk = list(card.get("needs") or [])
    while walk:
        need = walk.pop()
        if need in finished:
            continue                 # that wait is over; what it named is history
        if need == card.get("id"):
            return "its needs lead back to itself"
        if need in seen:
            continue
        seen.add(need)
        walk += list((by_id.get(need) or {}).get("needs") or [])
    return ""
