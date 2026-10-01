"""A card's budget: what its builder sessions have cost it, what is left, and which cards to review when it is gone.

A session's reported cost is its running total, so a resumed call replaces the card's spend and a fresh session
adds to it. A card that spends its budget is planned wrongly (too big, or its gate too slow): it is stopped, and
it and the cards after it are resliced or simplified before anything runs."""

from __future__ import annotations

import pathlib

import lean_spec
import project_specs
from providers import Outcome

BELL = 3.99       # dollars: past this a card is suspect, so the owner is told at once
CARD_BUDGET = 8   # dollars: past this it is stopped (a real card cost $163)


def spent(before: float, out: Outcome, resumed: bool) -> float:
    """The card's spend after a builder call: a resumed call's cost is the session's running total."""
    cost = out.cost if isinstance(out.cost, (int, float)) and not isinstance(out.cost, bool) else None
    if cost is None:
        return before
    return float(cost) if resumed else before + cost


def left(spent_so_far: float) -> float:
    """What a next call may spend."""
    return round(CARD_BUDGET - spent_so_far, 2)


def after(ws, task: dict, out: Outcome, before: float, resumed: bool) -> float:
    """The card's spend after a builder call; sets the cap for the next call, and rings the bell once when the
    card passes `BELL`: a mail, and the build carries on."""
    total = spent(before, out, resumed)
    task["budget"] = left(total)
    if total >= BELL and not task.get("bell"):
        task["bell"] = True
        ws.event("lean_bell", task=task["id"], spent=round(total, 2), budget=CARD_BUDGET)
        ws.mail_person(f"graph-loop: {task['id']} passed ${BELL}",
                       f"{task['id']} has cost ${total:.2f} so far. Its budget is ${CARD_BUDGET}: it is stopped "
                       "there, and it and the cards after it are then resliced or simplified.\n\nA card this "
                       "expensive is suspect: look at its spec and its worktree now. The build carries on.")
    return total


def stopped_words(spent_so_far: float) -> str:
    return (f"Reslice this card or speed up its gate: it spent ${spent_so_far:.2f} of its budget of ${CARD_BUDGET}, "
            "so it starts no repair")


def review_note(spec_path: str) -> str:
    """What the stop mail adds: reslice or simplify this card, and the next unbuilt ones, before any runs."""
    folder = pathlib.Path(spec_path).parent
    built = project_specs.built_names(str(folder.parent.parent)) or set()
    later = [path.stem for path in sorted(folder.glob("*.md"))
             if path.name not in dict(lean_spec.NOTES) and path.stem > pathlib.Path(spec_path).stem and path.stem not in built]
    named = f" and the cards after it: {', '.join(later[:5])}" if later else ""
    return f"\n\nReslice or simplify this card{named} before any of them runs: a card this expensive is a planning problem."
