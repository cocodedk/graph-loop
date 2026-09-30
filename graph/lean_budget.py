"""A card's budget: what its builder sessions have cost it, what is left, and which cards to review when it is gone.

A session's reported cost is its running total, so a resumed call replaces the card's spend and a fresh session
adds to it. A card that spends its budget is planned wrongly (too big, or its gate too slow): it is stopped, and
it and the cards after it are resliced or simplified before anything runs."""

from __future__ import annotations

import pathlib

import project_specs
from providers import Outcome

CARD_BUDGET = 8   # dollars: past $3.99 a card is suspect, past this it is stopped (a real card cost $163)


def spent(before: float, out: Outcome, resumed: bool) -> float:
    """The card's spend after a builder call: a resumed call's cost is the session's running total."""
    cost = out.cost if isinstance(out.cost, (int, float)) and not isinstance(out.cost, bool) else None
    if cost is None:
        return before
    return float(cost) if resumed else before + cost


def left(spent_so_far: float) -> float:
    """What a next call may spend."""
    return round(CARD_BUDGET - spent_so_far, 2)


def stopped_words(spent_so_far: float) -> str:
    return (f"the card spent ${spent_so_far:.2f} of its budget of ${CARD_BUDGET}: it is too big or its gate "
            "too slow, so it starts no repair")


def review_note(spec_path: str) -> str:
    """What the stop mail adds: reslice or simplify this card, and the next unbuilt ones, before any runs."""
    folder = pathlib.Path(spec_path).parent
    built = project_specs.built_names(str(folder.parent.parent)) or set()
    later = [path.stem for path in sorted(folder.glob("*.md"))
             if path.name != "lessons.md" and path.stem > pathlib.Path(spec_path).stem and path.stem not in built]
    named = f" and the cards after it: {', '.join(later[:5])}" if later else ""
    return f"\n\nReslice or simplify this card{named} before any of them runs: a card this expensive is a planning problem."
