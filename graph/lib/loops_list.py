"""The list of running lean loops, one line each."""

from __future__ import annotations

from collections.abc import Callable

import loops_projects
import loops_ps
import loops_step
import loops_waiting
from screen_color import paint, quiet

NONE_RUNNING = "no lean loops running"


def duration(seconds: int) -> str:
    """`45s`, `2m10s`, `1h05m`."""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m"


def report(ps_text: str, cwd_for: Callable[[int], str | None], now: float, color: bool = False) -> str:
    """The text to print for the loops in `ps_text`, by process id, then the recorded projects that wait for a
    person, their project and spec columns under the loops'; with `color` the step name is yellow from 5 minutes
    and red from 15, and `loop up …` is dim."""
    rows, spents = [], []
    found = loops_ps.found_in(ps_text, cwd_for)
    waiting = loops_waiting.rows(found, loops_projects.folders())
    for at, (loop, _) in enumerate(found, 1):
        name, spent = loops_step.step(loop.workspace, loop.age, now)
        spents.append(spent)
        rows.append([str(at), loop.project, loop.spec, name, duration(spent), loops_step.using(loop.workspace),
                     f"loop up {duration(loop.age)}"])
    if rows and not any(row[5] for row in rows):         # nothing to say about the call: no column
        for row in rows:
            del row[5]
    widths = [max((len(row[0]) for row in rows), default=-2) + 2,      # number, project, spec: the waiting rows share them
              max([len(row[1]) for row in rows] + [len(row[0]) for row in waiting], default=0) + 2,
              max([len(row[2]) for row in rows] + [len(row[1]) for row in waiting], default=0) + 2]
    tail = ["", *loops_waiting.lines(waiting, widths, color)] if waiting else []
    if not rows:
        return "\n".join([NONE_RUNNING, *tail])
    widths += [max(len(row[col]) for row in rows) + 2 for col in range(3, len(rows[0]) - 1)]

    def line(row: list[str], spent: int) -> str:
        cells = "".join(paint(cell, quiet(spent) if col == 3 else "", color) + " " * (width - len(cell))
                        for col, (cell, width) in enumerate(zip(row, widths)))
        return cells + paint(row[-1], "dim", color)
    return "\n".join([*(line(row, spent) for row, spent in zip(rows, spents)), *tail])
