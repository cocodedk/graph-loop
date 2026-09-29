"""The list of running lean loops, one line each."""

from __future__ import annotations

from collections.abc import Callable

import loops_ps
import loops_step

NONE_RUNNING = "no lean loops running"


def duration(seconds: int) -> str:
    """`45s`, `2m10s`, `1h05m`."""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m"


def report(ps_text: str, cwd_for: Callable[[int], str | None], now: float) -> str:
    """The text to print for the loops in `ps_text`, by process id."""
    rows = []
    for at, loop in enumerate(loops_ps.loops_in(ps_text, cwd_for), 1):
        name, spent = loops_step.step(loop.workspace, loop.age, now)
        rows.append([str(at), loop.project, loop.spec, name, duration(spent),
                     f"loop up {duration(loop.age)}"])
    if not rows:
        return NONE_RUNNING
    widths = [max(len(row[col]) for row in rows) + 2 for col in range(5)]
    return "\n".join("".join(cell.ljust(width) for cell, width in zip(row, widths)) + row[5]
                     for row in rows)
