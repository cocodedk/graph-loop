"""Classify durable lane endings, then route only their small consequences."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from backlog import Backlog
from triage_cards import write_cards as _write_cards
from triage_evidence import Ending, has_outcome, pending_endings
from triage_intelligence import decide_unknown
from triage_repairs import REPAIRS, sweep
from triage_routes import activate_preview, fire, preview_routes, routes
from triage_signatures import Decision, classify
from triage_state import valid_decision
from workspace import Workspace


def triage_pending(book: Backlog, space: Workspace,
                   call: Callable | None = None) -> list[Decision | None]:
    """Catch up once from the append-only log; the caller owns the turn."""
    prior = space.events()
    activate_preview(book, space, prior)
    prior = space.events()
    first = not any(row.get("kind") == "triage_preview" for row in prior)
    endings = pending_endings(book, space)
    if not endings:
        if first:
            _finish_preview(book, space)
        return []

    decisions, decision_rows, unknowns, exhausted = _decide(
        endings, prior, first, space, call)
    card_actions = _write_cards(book, endings, decisions)
    _sweeps(book, space, endings, decisions, first=first, prior=prior)
    alerts, proposals = routes(book, decision_rows, unknowns, exhausted)
    if not first:
        fire(space, alerts, proposals)
    _record(space, endings, decisions, card_actions)
    if first:
        _finish_preview(book, space)
    return decisions


def _decide(endings: list[Ending], prior: list[dict], first: bool,
            space: Workspace, call: Callable | None,
            ) -> tuple[list[Decision | None], list[dict], Counter, set[str]]:
    saved = {_key(row): row for row in prior if valid_decision(row)}
    used = {str(row.get("task")) for row in prior
            if row.get("kind") == "triage_model" and row.get("task")}
    pending = {_key(ending) for ending in endings}
    known_unknowns = {_key(row): str(row.get("task")) for row in prior
                      if row.get("kind") == "triage"
                      and row.get("verdict") == "unknown"
                      and row.get("signature") != "person-queued"
                      and _key(row) not in pending}
    unknowns = Counter(known_unknowns.values())
    decisions, rows, exhausted = [], [], set()
    for ending in endings:
        row = saved.get(_key(ending))
        if row is None:
            decision = classify(ending)
            if decision and decision.verdict == "unknown" \
                    and decision.signature != "person-queued" and not first:
                if not unknowns[ending.task] and ending.task not in used:
                    # on the platter before the call it pays for: this line is
                    # the whole of "this task has had its one" (finding 14)
                    space.event("triage_model", task=ending.task,
                                closed_at=ending.closed_at,
                                closed_index=ending.closed_index,
                                closed_kind=ending.closed_kind, synced=True)
                    used.add(ending.task)
                    decision = decide_unknown(ending, space, call=call)
                    if decision.verdict == "unknown":
                        exhausted.add(ending.task)
                elif ending.task in used:
                    exhausted.add(ending.task)
            row = _save_decision(space, ending, decision, first)
        else:
            decision = _read_decision(row)
        if decision and decision.verdict == "unknown" \
                and decision.signature != "person-queued":
            unknowns[ending.task] += 1
        decisions.append(decision)
        rows.append(row)
    return decisions, rows, unknowns, exhausted


def _save_decision(space: Workspace, ending: Ending,
                   decision: Decision | None, first: bool) -> dict:
    gate = str(ending.card.get("gate") or "")
    repair = REPAIRS.get(decision.signature) if decision else None
    why = (decision.why if decision else
           "work accepted" if has_outcome(ending)
           else "no outcome in this boundary")
    return space.event(
        "triage_decision", task=ending.task,
        verdict=decision.verdict if decision else None,
        signature=decision.signature if decision else None, why=why,
        repairable=bool(repair and repair(gate) != gate), catchup=first,
        accepted=_accepted(ending), closed_at=ending.closed_at,
        closed_index=ending.closed_index, closed_kind=ending.closed_kind)


def _read_decision(row: dict) -> Decision | None:
    verdict = row.get("verdict")
    if verdict is None:
        return None
    return Decision(str(verdict), str(row.get("signature") or "unknown"),
                    str(row.get("why") or ""))


def _sweeps(book: Backlog, space: Workspace, endings: list[Ending],
            decisions: list[Decision | None], *, first: bool,
            prior: list[dict]) -> None:
    persisted = {
        (str(row.get("signature")), tuple(row["source"])) for row in prior
        if row.get("kind") == "triage_sweep" and row.get("source")
        and bool(row.get("applied")) == (not first)
    }
    seen = set()
    for ending, decision in zip(endings, decisions, strict=True):
        if not decision or decision.signature not in REPAIRS \
                or decision.signature in seen:
            continue
        seen.add(decision.signature)
        source = _key(ending)
        if (decision.signature, source) not in persisted:
            sweep(book, space, decision.signature, apply=not first,
                  source=list(source))


def _record(space: Workspace, endings: list[Ending],
            decisions: list[Decision | None], actions: dict[int, str]) -> None:
    for ending, decision in zip(endings, decisions, strict=True):
        space.event("triage", task=ending.task,
                    verdict=decision.verdict if decision else None,
                    signature=decision.signature if decision else None,
                    why=(decision.why if decision else
                         "work accepted" if has_outcome(ending)
                         else "no outcome in this boundary"),
                    card=actions.get(ending.closed_index, "unchanged"),
                    closed_at=ending.closed_at, closed_index=ending.closed_index,
                    closed_kind=ending.closed_kind)


def _finish_preview(book: Backlog, space: Workspace) -> None:
    alerts, proposals = preview_routes(book, space.events())
    space.event("triage_preview", would_alert=alerts, would_propose=proposals)


def _key(row) -> tuple:
    return (row.task if isinstance(row, Ending) else row.get("task"),
            row.closed_at if isinstance(row, Ending) else row.get("closed_at"),
            row.closed_index if isinstance(row, Ending) else row.get("closed_index"),
            row.closed_kind if isinstance(row, Ending) else row.get("closed_kind"))


def _accepted(ending: Ending) -> bool:
    return any(row.get("kind") == "accepted" for row in ending.events)
