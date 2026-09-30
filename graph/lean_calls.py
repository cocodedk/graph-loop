"""The lean loop's four calls, each read from the LEAN block in `lib/models.py` when it is made."""

from __future__ import annotations

import models

PURPOSE = {"builder": "build", "repair": "build", "grill": "grill", "review": "review"}


def block(call: str) -> dict:
    """The `{"model", "effort"}` the block holds for `call` right now."""
    return models.LEAN[call]


def started(ws, call: str, task: str) -> dict:
    """Write `lean_call_started` for `call`, so a long step shows, and return its block entry."""
    use = block(call)
    ws.event("lean_call_started", purpose=PURPOSE[call], task=task, model=use["model"], effort=use["effort"])
    return use
