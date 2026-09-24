"""How large a task looks from its own shape.

Which model and effort actually build or review a card is `model_router.choose`'s
call now (docs/ROUTER.md) — a Jev decision at medium, raised only from a
recorded failed medium attempt, never a round counter alone. `weight` stays: it
is what a card's own shape says about it, read by callers outside the router.
"""

from __future__ import annotations

from backlog_status import is_live


def weight(task: dict) -> int:
    """0 for a one-file card, up to 3 for a live or commander-marked one."""
    score = 0
    if is_live(task):
        score += 2                      # a live card acts on the stack: think first
    if task.get("hard_review"):
        score += 2                      # the commander said so
    if len(task.get("files") or []) >= 4:
        score += 1
    if len(str(task.get("done_when") or "")) > 1200:
        score += 1                      # a long contract carries many rules
    return score
