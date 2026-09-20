"""Write only a card's TRIAGE verdict, preserving every other backlog byte."""

from __future__ import annotations

import pathlib
import re
import stat

import backlog_tree
import cardfile
from backlog_status import DONE, DROPPED

FINISHED = set(DONE + DROPPED)
VERDICT = re.compile(r"[a-z][a-z0-9_-]*")


def write_cards(book, endings: list, decisions: list) -> dict[int, str]:
    """Write each open task once from its latest actionable boundary."""
    chosen = {}
    for ending, decision in zip(endings, decisions, strict=True):
        if decision is not None or _accepted(ending):
            chosen[ending.task] = ending, decision
    actions = {}
    with book.only_writer():
        document = book.read()
        cards = {str(row.get("id")): row for row in document.get("tasks") or []}
        paths = document.get(backlog_tree.PATHS) or {}
        for task, (ending, decision) in chosen.items():
            card = cards.get(task)
            if not card or card.get("status") in FINISHED:
                continue
            verdict = decision.verdict if decision else None
            if card.get("triage") == verdict \
                    and (verdict is not None or "triage" not in card):
                continue
            if book.is_tree:
                _write_tree(paths[task], verdict)
            else:
                book.note(task, triage=verdict)
            actions[ending.closed_index] = verdict or "cleared"
    return actions


def _write_tree(path: pathlib.Path, verdict: str | None) -> None:
    """Patch the owning note's front matter; a whole-tree write loses legacy links.

    The body is not read and not written: a verdict is the loop's field, and the
    prose beneath it belongs to whoever wrote the card.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    if verdict is not None and VERDICT.fullmatch(verdict) is None:
        raise ValueError(f"invalid triage verdict: {verdict}")
    patched = cardfile.patch(text, "triage", verdict)
    if patched == text:
        return
    beside = path.with_suffix(f"{cardfile.SUFFIX}.new")
    with beside.open("w", encoding="utf-8", newline="") as handle:
        handle.write(patched)
    beside.chmod(stat.S_IMODE(path.stat().st_mode))
    beside.replace(path)


def _accepted(ending) -> bool:
    return any(row.get("kind") == "accepted" for row in ending.events)
