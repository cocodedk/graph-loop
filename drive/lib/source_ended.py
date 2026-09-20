"""How a campaign ends with its gaps recorded: the receipt, and reading it.

Split from `source_gap` at the 200-line cap; that file stays the one door and
re-exports these. `dropped` settles a dependency and does not prove the
requirement, so an exhausted source gap gets its own terminal result rather
than being counted as coverage (astra's section H 6).
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import durable
from finishing import SOURCE_GAP, declared_sources
from workspace_claims import _now

ENDED = "source-gap-ended.json"
BACKLOG = "the backlog"       # what ended, when it is the cards and not the sources


def end_with_gaps(space, book, request: str, decision: dict,
                  subject: str = SOURCE_GAP) -> None:
    """End the campaign with what it did not cover written down.

    `after` is how much log there was when this was written, because that is
    what says which declarations came SINCE: the clock steps in seconds, and a
    declaration inside the same second would otherwise leave the ending
    standing (an independent review, finding 3).

    `subject` is what ran out: the sources, or the backlog itself
    (`end_on_unproved_work`), which no model decided and which names no request.
    """
    rows = book.tasks()
    durable.replace(pathlib.Path(space.root) / ENDED, json.dumps(
        {"at": _now(), "after": len(space.events()), "request": request,
         "sources": declared_sources(space),
         "backlog": _digest(rows), "left": [str(row.get("id")) for row in rows
                                            if str(row.get("status")) not in ("done", "dropped")],
         # every drop and every card still owed, whole: `gaps` is the sentence a
         # reader is shown and is cut, and cutting was all this record had — the
         # cards past 400 characters lost their id and their reason with it
         # (an independent review, finding 2, and on another, finding 2).
         "dropped": dropped_work(space, rows),
         "unfinished": unfinished_work(space, book),
         "why": str(decision.get("why") or "")[:400],
         "gaps": str(decision.get("gap") or "")[:400]}, sort_keys=True, indent=1))
    space.event("ended_with_gaps", task=subject, decided_by_model=request,
                why=str(decision.get("gap") or decision.get("why") or "")[:300])


def end_on_unproved_work(space, book) -> dict | None:
    """End the campaign on the BACKLOG's own gaps, or None when it has none.

    Two kinds of gap, and neither of them is coverage. A card the loop DROPPED
    was decided against, never proved (astra's round-3 finding 20). A card still
    OWED when nothing can start it — a rejection nobody resolved, a card whose
    actor never came — was not proved either, and reading only the drops let a
    campaign whose last card stopped `rejected` return zero (astra's round-4
    finding 12). Nothing in the record says a done card covers what either one
    left, so both are reported, and a stand-down is a finish only when the
    backlog holds neither.

    No model decided this ending, so it names no request.
    """
    gone = dropped_work(space, book.tasks()) + unfinished_work(space, book)
    if not gone:
        return None
    end_with_gaps(space, book, "", {
        "why": "the backlog holds work that was never proved",
        "gap": "; ".join(f"{one['id']}: {one['why']}" for one in gone)}, subject=BACKLOG)
    return ended(space)


def unfinished_work(space, book) -> list[dict]:
    """Every card still owed, with the status it stopped in and its reason."""
    return [{"id": str(row.get("id")), "why": f"{row.get('status')}, {_why(space, row)}"}
            for row in book.unfinished()]


def dropped_work(space, rows: list[dict]) -> list[dict]:
    """Every card the loop dropped, with the whole reason it was dropped for —
    the receipt's own list, read from the backlog rather than kept beside it."""
    return [{"id": str(row.get("id")), "why": _why(space, row)}
            for row in rows if str(row.get("status")) == "dropped"]


def _why(space, row: dict) -> str:
    """Why this card was dropped: the card's own reason, or the `dropped` event
    that carried it when the card no longer says."""
    said = str(row.get("refused_why") or "").strip()
    if said:
        return said
    events = [str(one.get("why") or "") for one in space.events()
              if one.get("kind") == "dropped" and one.get("task") == row.get("id")]
    return (events[-1] if events else "") or "no reason recorded"


def ended(space) -> dict | None:
    """What this campaign ended with, or None. A declaration made since is a new
    question: the sources moved, so what was recorded is not this campaign's
    ending any more.

    "Since" is where the log stood when the receipt was written, never where the
    ending's own event sits: the receipt goes down before that event, so a death
    between the two would void a real ending — and with it the proof that the
    decision behind it ran.

    A receipt written before that position was recorded has only its clock, and
    that clock is read for it: taking the missing position as zero let the
    campaign's own FIRST declaration void a real ending (an independent review,
    finding 2). The clock steps in whole seconds, which is why new receipts
    carry the position.
    """
    try:
        row = json.loads((pathlib.Path(space.root) / ENDED).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    after, at = row.get("after"), str(row.get("at") or "")
    since = space.events()[int(after):] if after is not None else [
        one for one in space.events() if str(one.get("at") or "") > at]
    if any(one.get("kind") == "sources_declared" for one in since):
        return None
    return row


def _digest(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(
        sorted((str(row.get("id")), str(row.get("status"))) for row in rows),
        default=str).encode("utf-8")).hexdigest()[:16]


