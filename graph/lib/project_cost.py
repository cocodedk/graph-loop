"""What each spec cost the builder, read from the project's lean event log.

Claude reports a resumed call's cost as its session's running total (four identical tiny calls in one
session reported 0.066, 0.132, 0.199 and 0.265), so summing the calls of a run counts the same money over
and over. A run's builder calls are one session: it counts once, at its largest; a spec's runs add up."""

from __future__ import annotations

import glob
import json
import os
import re


def _rows(project: str):
    """Every event of the project's lean log, oldest first: the rotated parts, then the open one."""
    folder = os.path.join(project, "scratchpad", "lean")
    for path in sorted(glob.glob(os.path.join(folder, "events-*.jsonl"))) + [os.path.join(folder, "events.jsonl")]:
        try:
            with open(path, encoding="utf-8", errors="replace") as log:
                lines = log.read().splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def card_costs(project: str) -> dict[str, float]:
    """Dollars by spec name from `<project>/scratchpad/lean/events*.jsonl`; {} when there is no log."""
    runs: dict[tuple[str, int], float] = {}
    run = 0
    for row in _rows(project):
        if row.get("kind") == "lean_feature_started":
            run += 1
        elif row.get("kind") == "attempt" and row.get("purpose") == "build" and isinstance(row.get("task"), str):
            cost = row.get("cost")
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                key = (row["task"], run)
                runs[key] = max(runs.get(key, 0.0), float(cost))
    costs: dict[str, float] = {}
    for (task, _run), cost in runs.items():
        costs[task] = costs.get(task, 0.0) + cost
    return costs


def card_days(project: str) -> dict[str, str]:
    """The day (`YYYY-MM-DD`, UTC, as the log stamps it) of each spec's last event: for a finished spec, the day
    it was published or stopped. An event with no task or no dated `at` says nothing."""
    days: dict[str, str] = {}
    for row in _rows(project):
        task, at = row.get("task"), row.get("at")
        if isinstance(task, str) and isinstance(at, str) and re.match(r"\d{4}-\d{2}-\d{2}", at):
            days[task] = at[:10]
    return days


def card_turns(project: str) -> dict[str, int]:
    """The turns each spec's builder calls took, summed: a call reports its own turns, not its session's."""
    turns: dict[str, int] = {}
    for row in _rows(project):
        count = row.get("turns")
        if (row.get("kind") == "attempt" and row.get("purpose") == "build" and isinstance(row.get("task"), str)
                and isinstance(count, int) and not isinstance(count, bool)):
            turns[row["task"]] = turns.get(row["task"], 0) + count
    return turns


def card_models(project: str) -> dict[str, str]:
    """The model of each spec's last build call (`sonnet-5-5`), from the `lean_call_started` events that record
    it; a spec built before the model was recorded has none."""
    models: dict[str, str] = {}
    for row in _rows(project):
        task, model = row.get("task"), row.get("model")
        if row.get("kind") == "lean_call_started" and row.get("purpose") == "build" and isinstance(task, str) \
                and isinstance(model, str) and model:
            models[task] = model.removeprefix("claude-")
    return models
