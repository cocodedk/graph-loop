"""The routes out of TRIAGE, including one named preview approval."""

from __future__ import annotations

from collections import Counter

from backlog_status import DONE, DROPPED
from triage_effect import write_effect
from triage_preview import APPROVAL, acts, approved, effects_of, open_actions, refused
from triage_repairs import REPAIRS, facing
from triage_state import valid_decision

FINISHED = set(DONE + DROPPED)
MECHANICAL = ("gate", "rig", "environment")


def activate_preview(book, space, rows: list[dict]) -> None:
    """Activate exactly the preview a decision approved, once — everything
    under ONE hold of the backlog lock, because what is approved is read from
    the cards and the sweep then writes them."""
    with book.only_writer():
        _activate(book, space, rows)


def _activate(book, space, rows: list[dict]) -> None:
    """What it would do is read once, by `triage_preview.effects_of`, and the
    approver is shown that same reading: approval binds the sweeps as well as the
    two arrays, which say nothing about them.

    Three endings need no approval at all. A preview already activated is done.
    A preview a decision refused is over — the receipt is read from the platter,
    because an event nobody reads leaves it waiting for ever. And a preview that
    would do nothing is consumed mechanically, with no decision and no model
    call; its `triage_activation` is that receipt.
    """
    facts = effects_of(book, rows)
    if facts is None:
        return
    index = facts["index"]
    if any(row.get("kind") == "triage_activation"
           and row.get("preview_index") == index for row in rows) \
            or refused(space, index):
        return
    standing = approved(space, index)
    if standing is None:
        if not acts(facts):
            space.event("triage_activation", preview_index=index, sweeps=[],
                        why="the preview would do nothing: consumed with no decision")
            return
        # Said once, because the board is how anyone SEES what the loop is
        # doing — never a handoff. The decider used to write this approval and
        # nothing writes it since it was cut, so the preview stays unapplied:
        # the card keeps its own next actor, which is the plan phase.
        _alert_once(space, rows, "the triage",
                    f"TRIAGE preview {index} is approved by nobody; nothing in "
                    f"{space.root / APPROVAL} approves what it would do")
        return
    _apply(book, space, rows, index, standing)


def _apply(book, space, rows: list[dict], index: int, standing: dict) -> None:
    """Do what was approved, and finish what a death left half done.

    ONE rule decides whether a repair may run: apply it only if the card is
    exactly what the approval says it will find, in every field the repair reads
    — gate, liveness and open-or-not (`triage_repairs.facing`). Anything else is
    a card nobody reviewed, and the activation stops where it stands.

    What it does is what the approval HOLDS — the gate, the status and the
    rounds recorded for each card — never a repair asked again what it would do
    now: a repair edited between the approval and this landed text nobody had
    reviewed under that approval (astra's round-4 finding 11).

    A repair that has already run is not asked that question: its own
    `triage_sweep` record, or — when a death lost that record — the cards
    already holding the gate it would write, which is this loop's own work.

    Nothing is carried over from the repairs before it. The approval says what
    each will find, folded in the preview where the folding belongs; reading a
    predecessor's approved "after" here instead of the card hid an edit that
    landed between the two.
    """
    given = standing.get("effects") or {}
    who = str(standing.get("request") or "")
    applied = {
        (row.get("preview_index"), str(row.get("signature")),
         tuple(str(task) for task in row.get("scope") or []))
        for row in rows if row.get("kind") == "triage_sweep" and row.get("applied")
    }
    for one in given.get("sweeps") or []:
        if (index, one["signature"], tuple(one["scope"])) in applied or _ours(book, one):
            continue         # this repair has run: its record, or its own work
        if facing(book, one["scope"]) != one.get("facing"):
            _alert_once(space, rows, "the triage",
                        f"TRIAGE preview {index} was approved for {one['signature']} "
                        "over cards that are not what it would find now; it is not applied")
            return
        apply_sweep(book, space, index, one)
    # Filtered again at the moment they fire: they were read when the decision
    # was made, and a card can finish between the two.
    fire(space, open_actions(book, given.get("would_alert") or []),
         open_actions(book, given.get("would_propose") or []))
    # The request named in the approval is stamped on what this produced, so the
    # decision that approved it can prove its own effect ran.
    space.event("triage_activation", preview_index=index, decided_by_model=who,
                sweeps=[one["signature"] for one in given.get("sweeps") or []])


def apply_sweep(book, space, index: int, one: dict) -> None:
    """Write exactly the effects this repair was approved for, and record the
    sweep the way `triage_repairs.sweep` records its own.

    The cards go first and the record after, as the mechanical sweep does: a
    death between the two leaves the repair landed and unrecorded, which `_ours`
    reads back as this loop's own work.
    """
    for task_id, effect in (one["changes"] or {}).items():
        write_effect(book, space, task_id, effect)
    for task_id in one["live"]:
        space.alert(task_id,
                    f"triage found {one['signature']} in a live gate; fix it by hand")
    space.event("triage_sweep", signature=one["signature"],
                repair=getattr(REPAIRS.get(one["signature"]), "__name__", ""),
                applied=True, tasks=list(one["changes"] or {}), live=list(one["live"]),
                source=None, scope=list(one["scope"]), preview_index=index)


def _ours(book, one: dict) -> bool:
    """Whether the cards this repair names already hold the gate it would write.

    The effects are written under the lock and recorded after, so a death
    between the two leaves the repair landed and unrecorded. Reading that as
    somebody editing the gate stopped the activation for good, when it is this
    loop's own work.
    """
    return bool(one["changes"]) and all(
        str((book.task(task) or {}).get("gate") or "") == effect["gate"]
        for task, effect in one["changes"].items())


def routes(book, rows: list[dict], unknowns: Counter,
           exhausted: set[str] | None = None) -> tuple[list[dict], list[dict]]:
    """Route only each task's latest row; an empty latest row routes nowhere."""
    latest = {str(row.get("task")): row for row in rows if row.get("task")}
    alerts, proposals = [], []
    for task, row in latest.items():
        card = book.task(task)
        verdict = row.get("verdict")
        if not card or card.get("status") in FINISHED or verdict is None:
            continue
        if verdict == "harness":
            proposals.append(_action(row))
        elif verdict in MECHANICAL and not row.get("repairable"):
            alerts.append(_action(row))
        elif verdict == "unknown" and row.get("signature") != "person-queued" \
                and (unknowns[task] >= 2 or task in (exhausted or set())):
            action = _action(row)
            action["why"] = f"unknown twice: {row.get('why') or ''}"
            alerts.append(action)
    return alerts, proposals


def preview_routes(book, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    decisions = [row for row in rows if valid_decision(row) and row["catchup"]]
    unknowns = Counter(str(row.get("task")) for row in decisions
                       if row.get("verdict") == "unknown"
                       and row.get("signature") != "person-queued")
    alerts, proposals = routes(book, decisions, unknowns)
    for proposal in proposals:
        proposal["evidence"] = [
            {key: row.get(key) for key in ("task", "closed_at", "closed_index", "why")}
            for row in decisions if row.get("signature") == proposal["signature"]]
    return alerts, proposals


def fire(space, alerts: list[dict], proposals: list[dict]) -> None:
    """Fire stored routes idempotently; a replay cannot duplicate the board."""
    prior = space.events()
    old_proposals = {(row.get("task"), row.get("closed_index")) for row in prior
                     if row.get("kind") == "triage_proposal"}
    for row in alerts:
        message = (f"triage ending {row['closed_index']}: {row['verdict']} needs a "
                   f"person [{row['signature']}] — {row['why']}")
        _alert_once(space, prior, str(row["task"]), message)
    for row in proposals:
        key = row.get("task"), row.get("closed_index")
        if key not in old_proposals:
            space.event("triage_proposal", **row)


def _action(row: dict) -> dict:
    keys = ("task", "verdict", "signature", "closed_at", "closed_index", "why")
    return {key: row.get(key) for key in keys}


def _alert_once(space, rows: list[dict], task: str, message: str) -> None:
    if not any(row.get("kind") == "alert" and row.get("task") == task
               and row.get("why") == message for row in rows):
        space.alert(task, message)
