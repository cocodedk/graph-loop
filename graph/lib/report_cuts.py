"""The cut check's share of a campaign's report, summed from the slicer's trace.

The plan phase writes one `cut_checked` line beside the backlog for every
molecule it checks (`slicer_answer._checked`), whether the check ran, found
something or failed. Reading them back tells a person what the check cost and
what it bought.
"""

from __future__ import annotations

import json
import pathlib

from campaign_of import backlog_of

KEYS = ("requests", "seconds", "usable", "merges", "findings")


def _number(value, kind):
    try:
        return kind(value or 0)
    except (TypeError, ValueError):
        return kind(0)


def _lines(space) -> list[dict]:
    """Every `cut_checked` line in the trace; none when the campaign has no
    backlog yet, no trace, or a line that is not JSON."""
    backlog = backlog_of(space)
    if not backlog:
        return []
    try:
        text = (pathlib.Path(backlog) / ".slicer-trace.jsonl").read_text("utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    found = []
    for raw in text.splitlines():
        try:
            line = json.loads(raw)
        except ValueError:
            continue
        if isinstance(line, dict) and line.get("step") == "cut_checked":
            found.append(line)
    return found


def cuts(space) -> dict:
    lines = _lines(space)
    total = {"runs": len(lines)}
    for key in KEYS:
        kind = float if key == "seconds" else int
        total[key] = sum(_number(line.get(key), kind) for line in lines)
    total["seconds"] = round(total["seconds"], 1)
    total["failures"] = sum(1 for line in lines if line.get("failed"))
    return total


def cut_line(out: dict) -> str:
    """The one line `as_text` prints for the cut check."""
    entry = out["cuts"]
    if not entry["runs"]:
        return "Cut check: none ran"
    return (f"Cut check: {entry['runs']} runs, {entry['requests']} requests, "
            f"{entry['seconds']}s, usable {entry['usable']}, merges {entry['merges']}, "
            f"findings {entry['findings']}, failures {entry['failures']}")
