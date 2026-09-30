"""What each spec cost the builder, read from the project's lean event log.

Claude reports a resumed call's cost as its session's running total (four identical tiny calls in one
session reported 0.066, 0.132, 0.199 and 0.265), so summing the calls of a run counts the same money over
and over. A run's builder calls are one session: it counts once, at its largest; a spec's runs add up."""

from __future__ import annotations

import glob
import json
import os


def card_costs(project: str) -> dict[str, float]:
    """Dollars by spec name from `<project>/scratchpad/lean/events*.jsonl`; {} when there is no log."""
    folder = os.path.join(project, "scratchpad", "lean")
    files = sorted(glob.glob(os.path.join(folder, "events-*.jsonl"))) + [os.path.join(folder, "events.jsonl")]
    runs: dict[tuple[str, int], float] = {}
    run = 0
    for path in files:
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
            if not isinstance(row, dict):
                continue
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
