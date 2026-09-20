"""The small repairs TRIAGE may make without deciding what work means."""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable

from backlog import Backlog
from triage_effect import READS, repair_effect, write_effect
from workspace import Workspace

PIPE = re.compile(
    r"\(cd (?P<cwd>simulation(?:/[\w.-]+)*) && "
    r"(?P<command>timeout \d+ python3\b[^()]*) 2>&1 \| "
    r"(?P<tail>tail -\d+) \| "
    r"(?P<grade>grep -q[A-Za-z]* (?:'[^']*'|\"[^\"]*\"))\)",
)
PYTHON = re.compile(
    r"(?P<prefix>\(cd (?P<cwd>simulation(?:/[\w.-]+)*) && "
    r"(?:OUT=\$\()?timeout \d+ )python3\b"
)


def print_then_grade(gate: str) -> str:
    """Expose a parenthesised Python gate leg without changing its test."""
    def replace(found: re.Match[str]) -> str:
        return (f"(cd {found['cwd']} && OUT=$({found['command']} 2>&1); RC=$?; "
                f'echo "$OUT" | tail -8; [ $RC -eq 0 ] && echo "$OUT" | '
                f"{found['tail']} | {found['grade']})")

    return PIPE.sub(replace, gate)


def use_venv(gate: str) -> str:
    """Run Python from simulation/.venv in the gate directories we can prove."""
    def replace(found: re.Match[str]) -> str:
        depth = len(found["cwd"].split("/")) - 1
        python = "../" * depth + ".venv/bin/python3"
        return found["prefix"] + python

    return PYTHON.sub(replace, print_then_grade(gate))


REPAIRS: dict[str, Callable[[str], str]] = {
    "mute-gate": print_then_grade,
    "scrubbed-python": use_venv,
}


def facing(book: Backlog, scope, ahead: dict[str, dict] | None = None) -> dict:
    """What a repair will FIND on the cards it may touch: every field it reads
    (`triage_effect.READS`), and whether the card is still open.

    This projection IS the repair's input — `repair_effect` is handed it and can
    read nothing else — so what an approval records is what the repair reads,
    and a hand-written list of the fields that seemed to matter cannot drift
    from the code that reads them. An approval records this, and its activation
    asks the backlog the one question that matters: is this still that card?

    `ahead` is the effects the repairs before it in the same approval will have
    written, folded in over the same fields, which is how a preview says what
    the second of two on one card will find.
    """
    alive = {str(row.get("id")) for row in book.unfinished()}
    met = {}
    for task in sorted(scope):
        card = book.task(task) or {}
        found = {key: card.get(key) for key in READS}
        found.update({key: value for key, value in (ahead or {}).get(task, {}).items()
                      if key in READS})
        met[task] = {**found, "open": task in alive}
    return met


def would_change(book: Backlog, signature: str, task_ids: set[str] | None = None,
                 ahead: dict[str, dict] | None = None) -> tuple[dict, dict, list[str]]:
    """What this repair would really do, asked without doing any of it: the
    cards as it will FIND them, the whole effect it would write on each card it
    changes, and the LIVE matches it may only alert about.

    One reading of those cards, handed back with the answer: asking `facing`
    again beside this is two readings of one thing, and the second can disagree.

    The one eligibility rule, so what a preview is approved on and what its
    sweep then does cannot disagree (an independent review): a card that has
    finished is not swept, and a gate the repair leaves alone is not a change
    at all.
    """
    repair = REPAIRS.get(signature)
    scope = sorted(task_ids) if task_ids is not None else \
        [str(row["id"]) for row in book.unfinished()]
    met = facing(book, scope, ahead)
    if repair is None:
        return met, {}, []
    changes: dict[str, dict] = {}
    live: list[str] = []
    for task_id, found in met.items():
        if not found["open"]:
            continue
        gate = str(found["gate"] or "")
        fixed = repair(gate)
        if fixed == gate:
            continue
        if found["gate_has_side_effects"] or not found["files"]:
            live.append(task_id)
            continue
        changes[task_id] = repair_effect(found, fixed)
    return met, changes, live


def sweep(book: Backlog, space: Workspace, signature: str, *,
          apply: bool = True, task_ids: set[str] | None = None,
          source: list | None = None,
          preview_index: int | None = None) -> list[str]:
    """Apply one proved repair to matching open cards and record one sweep.

    The mechanical path, where nothing was approved: what it writes is what it
    has just read, under the lock. An approved preview does NOT come through
    here — it applies the effects its own approval holds (`triage_routes`).
    """
    repair = REPAIRS.get(signature)
    if repair is None:
        return []
    lock = book.only_writer() if apply else contextlib.nullcontext()
    with lock:
        # Asked inside the lock, so what is written is what was just read.
        _met, changes, live = would_change(book, signature, task_ids)
        changed = list(changes)
        if apply:
            for task_id, effect in changes.items():
                write_effect(book, space, task_id, effect)
    if apply:
        for task_id in live:
            space.alert(task_id, f"triage found {signature} in a live gate; fix it by hand")
    space.event("triage_sweep", signature=signature, repair=repair.__name__,
                applied=apply, tasks=changed, live=live, source=source,
                scope=sorted(task_ids) if task_ids is not None else None,
                preview_index=preview_index)
    return changed
