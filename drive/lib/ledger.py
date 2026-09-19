"""What happened, one line each: when, which card, what came of it.

The owner, 2026-08-31: "i want also a report which is date and time and result. no
textual bullshit." He read three hourly reports of mine while the loop landed
nothing and could not tell it was stuck, because the sentence that mattered was
buried in prose.

Written from the event log by code, never by hand. Oldest first, so the newest
line is the last one on the screen.
"""

from __future__ import annotations

# Only outcomes: what became of a card. Every other event is bookkeeping.
# `needs_a_person` is the builder's own word; what it means now is that no lane
# will take the card and the next plan phase does, so the line says NEEDS A
# DECISION and `decided` shows the answer that followed.
OUTCOME = {
    "accepted": "KEPT",
    "rejected": "REJECTED",
    "refused": "REFUSED",
    "failed": "FAILED",
    "dropped": "DROPPED",
    "needs_a_person": "NEEDS A DECISION",
    "decided": "DECIDED",
}
# `abandoned` names its cards in `tasks`, a list, not `task` — reading the
# writer, not the name: workspace_claims writes one event for the whole sweep.
MANY = {"abandoned": "ABANDONED"}
# UNCLEAR is NOT here: the builder's last line was unreadable, the loop alerts and
# the gate still judges, so the card has not ended and would otherwise show
# UNCLEAR and then KEPT.
STOPPED = {"BLOCKED": "STOPPED", "PARTIAL": "PARTIAL"}


def rows(events: list[dict]) -> list[tuple[str, str, str]]:
    """(when, card, result) for every event that ended a card's attempt."""
    out, stopped = [], set()
    for event in events:
        when, kind = str(event.get("at") or ""), str(event.get("kind") or "")
        if kind in MANY:
            out += [(when, str(one), MANY[kind]) for one in (event.get("tasks") or [])]
            continue
        task = str(event.get("task") or "")
        if not task:
            continue
        result = OUTCOME.get(kind)
        if kind == "said":                      # the builder's own last word
            result = STOPPED.get(str(event.get("state") or "").upper())
            if result:
                stopped.add(task)
        if kind == "needs_a_person" and task in stopped:
            stopped.discard(task)   # once only: a later call for a person is its own line
            continue                # the card just said STOPPED or PARTIAL for itself
        if result:
            out.append((when, task, result))
    return out


def text(events: list[dict], limit: int = 40) -> str:
    """The ledger as a person reads it: when, card, result. Nothing else."""
    lines = rows(events)[-limit:]
    if not lines:
        return "no outcomes recorded"
    wide = max(len(task) for _, task, _ in lines)
    return "\n".join(f"{when.replace('T', ' ').rstrip('Z')}  {task:<{wide}}  {result}"
                     for when, task, result in lines)
