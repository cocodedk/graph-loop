"""What a TRIAGE preview would actually do, read once for both readers.

Whoever approves is shown this and the activation applies this, so what is approved
is what happens. Reading them apart is the defect astra's section F names: the
activation gathers its dry sweeps from the log and applies their stored scopes,
while `would_alert` and `would_propose` say nothing about them, so an empty pair
of arrays never proved an empty preview.

A refusal is written down here too, durably, because `activate_preview` reads
it: an event saying "refused" that nothing reads leaves the same preview
waiting for ever.
"""

from __future__ import annotations

import json
import pathlib

import durable
from backlog_status import DONE, DROPPED
from triage_repairs import would_change
from workspace_claims import _now

FINISHED = set(DONE + DROPPED)

PREVIEWS = "previews"     # where a refused preview's receipt is written
APPROVAL = "triage-approved"     # the marker the activation reads as its authority


def effects_of(book, rows: list[dict]) -> dict | None:
    """The exact effects the newest preview would have, or None when there is
    no preview at all.

    The dry sweeps come first because they are what the arrays leave out: every
    unapplied `triage_sweep` before the preview, first of each signature, with
    the exact scope its activation would use. What each one would DO is asked of
    the backlog as it stands, through the rule the sweep itself walks
    (`triage_repairs.would_change`): every field it would write on every card it
    changes — the gate, and the status and the rounds that go back with it — and
    the LIVE matches it may only alert about. They are asked in the order they
    will RUN — each against what the ones before it leave — because two repairs
    on one card each asked against the gate as it stands expected the same
    "before", and the first to land made the second look edited. Each keeps the
    cards it EXPECTS TO FIND as well as what it would write, in one reading, so
    the activation can check a pending repair against the backlog itself rather
    than against what its predecessors were supposed to leave.

    A stored scope and a list of statuses said nothing about that text, so a
    gate edited after approval was repaired anyway, and a scope whose cards had
    all finished still bought a model call for a sweep that changes nothing.

    The routes are the open ones, filtered here as activation fires them: a
    route for a card that has finished is not fired and is not an effect.
    """
    previews = [(index, row) for index, row in enumerate(rows)
                if row.get("kind") == "triage_preview"]
    if not previews:
        return None
    index, preview = previews[-1]
    sweeps: list[dict] = []
    seen: list[str] = []
    ahead: dict[str, dict] = {}    # what the sweeps before this one will leave
    for row in rows[:index]:
        signature = str(row.get("signature") or "")
        if row.get("kind") == "triage_sweep" and not row.get("applied") \
                and signature not in seen:
            seen.append(signature)
            scope = sorted({str(task) for task in row.get("tasks", []) + row.get("live", [])})
            met, changes, live = would_change(book, signature, set(scope), ahead)
            ahead.update(changes)
            sweeps.append({"signature": signature, "scope": scope, "facing": met,
                           "changes": dict(sorted(changes.items())), "live": sorted(live)})
    alerts = open_actions(book, preview.get("would_alert") or [])
    proposals = open_actions(book, preview.get("would_propose") or [])
    named = sorted({task for sweep in sweeps for task in sweep["scope"]}
                   | {str(row.get("task")) for row in alerts + proposals})
    return {"index": index, "sweeps": sweeps, "would_alert": alerts,
            "would_propose": proposals,
            "cards": {task: str((book.task(task) or {}).get("status") or "gone")
                      for task in named}}


def open_actions(book, actions: list[dict]) -> list[dict]:
    """The routes still worth firing: a delayed approval cannot act on work that
    has since finished. One filter, read here and fired by `triage_routes`."""
    return [dict(row) for row in actions
            if (card := book.task(str(row.get("task"))))
            and card.get("status") not in FINISHED]


def acts(facts: dict) -> bool:
    """Whether this preview would do anything at all. A preview that would not
    is consumed mechanically, with no decision and no model call — a sweep whose
    cards have all finished, or whose gates no longer match, is not an effect."""
    return bool(any(one["changes"] or one["live"] for one in facts["sweeps"])
                or facts["would_alert"] or facts["would_propose"])


def said(facts: dict) -> str:
    """This preview's effects, as an approver is shown them: the sweeps first,
    then the routes, then every card either would touch and the status it holds
    now. Nothing is summarised — approval binds exactly this."""
    lines = [f"  preview {facts['index']}, as the log holds it"]
    for one in facts["sweeps"]:
        lines.append(f"  it would sweep {one['signature']} over: "
                     f"{', '.join(one['scope']) or '(nothing)'}")
        for task, effect in one["changes"].items():
            lines.append(f"    {task}'s gate would become: {effect['gate']}")
            if effect.get("status"):
                lines.append(f"    {task} would go back to its builder as "
                             f"{effect['status']}, with "
                             f"{effect.get('gate_rounds_refunded') or 0} round(s) refunded")
            if effect.get("alert"):
                lines.append(f"    {task} would be told: {effect['alert']}")
        lines += [f"    {task} is a LIVE match: it is alerted about, never edited"
                  for task in one["live"]]
    if not facts["sweeps"]:
        lines.append("  it would sweep nothing")
    for name, rows in (("alert", facts["would_alert"]), ("propose", facts["would_propose"])):
        lines += [f"  it would {name} for {row.get('task')}: {row.get('verdict')} "
                  f"[{row.get('signature')}] — {row.get('why')}" for row in rows]
    lines += [f"  {task} is {status} now" for task, status in facts["cards"].items()]
    return "\n".join(lines) + "\n"


def approve(space, facts: dict, request: str = "") -> pathlib.Path:
    """Write the approval: the effects that were reviewed, WHOLE, and who
    approved them.

    Recorded, never recomputed later. Activation's own first sweep changes the
    gates a recomputation would read, so a restart in the middle of it called
    its own progress an external edit and refused the routes nobody had fired
    yet (Codex, finding 1). Durable, because the activation that reads this may
    be a later turn's — and that turn stamps what it does with the request named
    here, so a decision can tell its own effect from a subject that merely
    stopped waiting.
    """
    return durable.replace(pathlib.Path(space.root) / APPROVAL,
                           json.dumps({"request": request, "effects": facts},
                                      sort_keys=True, indent=1))


def approved(space, index: int) -> dict | None:
    """The approval standing for this preview, or None. An approval for another
    preview approves nothing here; whether the world still matches what it
    holds is asked effect by effect, by whoever applies them."""
    try:
        row = json.loads((pathlib.Path(space.root) / APPROVAL).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    effects = row.get("effects") or {}
    return row if str(effects.get("index")) == str(index) else None


def refused_by(space, index: int) -> str:
    """The request whose refusal is already on the platter for this preview.

    The receipt is written before the event that announces it, so this is what
    says the refusal RAN when the driver died between the two (Codex,
    finding 2)."""
    try:
        row = json.loads(receipt_path(space, index).read_text("utf-8"))
    except (OSError, ValueError):
        return ""
    return str(row.get("request") or "")


def receipt_path(space, index: int) -> pathlib.Path:
    return pathlib.Path(space.root) / PREVIEWS / f"{index}.json"


def refused(space, index: int) -> str:
    """Why this preview was refused, or "" when it was not. Read from the
    platter, never from the event log: this is what stops the preview waiting."""
    try:
        row = json.loads(receipt_path(space, index).read_text("utf-8"))
    except (OSError, ValueError):
        return ""
    return str(row.get("why") or "refused")


def refuse(space, index: int, decision: dict, request: str) -> None:
    """End this preview for good: nothing it proposed happens, and the cards it
    named keep whatever actor they already have."""
    durable.replace(receipt_path(space, index), json.dumps(
        {"index": index, "at": _now(), "request": request,
         "why": str(decision.get("why") or "")[:400],
         "gap": str(decision.get("gap") or "")[:400]}, sort_keys=True, indent=1))
    space.event("triage_preview_refused", task=f"preview-{index}",
                preview_index=index, decided_by_model=request,
                why=str(decision.get("why") or "")[:300])
