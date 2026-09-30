"""When a project's lean loop is idle and a branch waits on the owner: the ladder, the message and the state.

The loop exits after it opens a pull request and the next spec refuses to start while any branch on origin is
unmerged, so a merge can wait for days with nothing to say so. This is checked from cron, once per run: it
mails at 30 minutes, 4 hours and 24 hours after it first sees the same set of branches, never two within an
hour, then stays silent until the set changes. One small state file in the workspace keeps the count."""

from __future__ import annotations

import json
import os
from collections.abc import Callable

import loops_ps

LADDER = (30 * 60, 4 * 3600, 24 * 3600)   # seconds after the first sighting of the same set of branches
GAP = 3600                                # never two mails within an hour


def step(state: dict, branches: list[str], running: bool, now: float) -> tuple[str, dict]:
    """What to do now: "quiet" (a loop runs), "clear" (nothing waits), "send" or "wait", and the new state."""
    if running:
        return "quiet", state
    if not branches:
        return "clear", {}
    key = "\n".join(sorted(branches))
    if state.get("key") != key:                       # a changed set is a new incident
        state = {"key": key, "since": now, "sent": 0, "last": None}
    count = state["sent"]
    spaced = state["last"] is None or now - state["last"] >= GAP
    if count < len(LADDER) and now - state["since"] >= LADDER[count] and spaced:
        return "send", state
    return "wait", state


def sent(state: dict, now: float) -> dict:
    """The state once a mail was accepted."""
    return {**state, "sent": state["sent"] + 1, "last": now}


def message(project: str, branches: list[str], number: int) -> tuple[str, str]:
    """The subject and the body of reminder `number`."""
    listed = "\n".join(f"- {name}" for name in sorted(branches))
    body = (f"The lean loop for {project} is idle: nothing is running, and these branches on origin "
            f"are not merged:\n\n{listed}\n\n"
            "They await your review and merge. The next spec will not start until they are merged or "
            "deleted; delete a branch that is already merged.\n\n"
            f"This is reminder {number} of {len(LADDER)}; it stays quiet after that until the list changes.")
    return f"the loop is idle: {project} awaits your review and merge", body


def _load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def _save(path: str, state: dict) -> None:
    if not state:
        if os.path.exists(path):
            os.unlink(path)
        return
    temp = f"{path}.tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    os.replace(temp, path)


def remind(repo: str, workspace: str, *, now: float, ps_text: str, cwd_for: Callable[[int], str | None],
           unmerged: Callable[[str], list[str]], mail: Callable[[str, str], bool]) -> str:
    """Check once. One line for the cron log: what it did."""
    here = os.path.realpath(repo)
    running = any(found and os.path.realpath(found) == here for _, found in loops_ps.found_in(ps_text, cwd_for))
    branches = [] if running else unmerged(repo)
    path = os.path.join(workspace, "remind.json")
    action, state = step(_load(path), branches, running, now)
    if action == "send":
        subject, body = message(os.path.basename(here), branches, state["sent"] + 1)
        if mail(subject, body):
            state = sent(state, now)
        else:
            action = "send failed"
    if action != "quiet":
        _save(path, state)
    return f"{os.path.basename(here)}: {action}"
