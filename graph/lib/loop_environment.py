"""A missing toolchain ends the driver, leaving the card's status and rounds alone."""

from __future__ import annotations

from loop_types import TaskOutcome
from provider_words import environment_hint
from watchdog_spin import current_run


def environment_ending(loop, task, tree, output: str, gate: str, step: str):
    remedy = environment_hint(output, gate)
    if not remedy:
        return None
    tree.keep(f"environment: {remedy}")
    loop.space.event("environment", task=task["id"], step=step,
                     why=output[-2000:], remedy=remedy, charged=False)
    return TaskOutcome("environment", remedy, tree.path)


def environment_stop(space) -> str:
    """One driver alert, before triage, replan, or watchdog can touch this ending."""
    rows = current_run(space.events())
    failures = [row for row in rows if row.get("kind") == "environment"]
    if not failures:
        return ""
    remedies = list(dict.fromkeys(row["remedy"] for row in failures))
    why = "missing gate toolchain: " + "; ".join(remedies)
    if not any(row.get("kind") == "alert"
               and str(row.get("why") or "").startswith("missing gate toolchain:") for row in rows):
        space.alert("the campaign", why, limit=None)
    return why
