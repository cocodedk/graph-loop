"""What a running lean loop is doing: the last event of its log, and how long ago it was."""

from __future__ import annotations

import calendar
import json
import os
import time

STEPS = {"grill": "grilling", "build": "building", "review": "reviewing"}


def when(row: object) -> float | None:
    """The epoch second of an event's `at` (UTC, `2026-09-28T19:36:22Z`), None when it has none."""
    try:
        return calendar.timegm(time.strptime(row["at"], "%Y-%m-%dT%H:%M:%SZ"))   # type: ignore[index]
    except (KeyError, TypeError, ValueError):
        return None


def last_event(workspace: str | None) -> dict | None:
    """The last line of `<workspace>/events.jsonl` that is an event; broken lines are skipped."""
    if not workspace:
        return None
    try:
        with open(os.path.join(workspace, "events.jsonl"), encoding="utf-8", errors="replace") as log:
            lines = log.read().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and when(row) is not None:
            return row
    return None


def step(workspace: str | None, age: int, now: float) -> tuple[str, int]:
    """The step's name and the seconds spent in it."""
    row = last_event(workspace)
    if row is None:
        return "starting", age
    since = max(0, int(now - when(row)))   # type: ignore[operator]
    purpose = row.get("purpose")
    if row.get("kind") == "lean_call_started" and isinstance(purpose, str) and purpose in STEPS:
        return STEPS[purpose], since
    return "working", since


def using(workspace: str | None) -> str:
    """The model and effort of the call a loop is making, `sonnet-5-5 high`: read from the last event when it
    is a call that started (older events carry the effort alone); "" otherwise."""
    row = last_event(workspace)
    if row is None or row.get("kind") != "lean_call_started":
        return ""
    model, effort = row.get("model"), row.get("effort")
    words = [model.removeprefix("claude-") if isinstance(model, str) else "", effort if isinstance(effort, str) else ""]
    return " ".join(word for word in words if word)
