"""The live screen: the list of loops, the selected project's view, and the key line."""

from __future__ import annotations

import os
from collections.abc import Callable

import loops_list
import loops_ps
import project_view
from screen_color import paint

KEYS = "keys: 1-9 switch loop · f filter ({}) · q quit · every {}s"


def folder(number: int, ps_text: str, cwd_for: Callable[[int], str | None]) -> str:
    """The project folder of loop `number` in the list; empty when there is no such loop or its
    folder cannot be resolved."""
    found = loops_ps.found_in(ps_text, cwd_for)
    return (found[number - 1][1] or "") if 1 <= number <= len(found) else ""


def screen(which: str | None, only: str | None, refresh: str, once: bool, ps_text: str,
           cwd_for: Callable[[int], str | None], now: float, rows: int | None = None, color: bool = False) -> str:
    """The whole screen: the list, the project view of `which` (or of the first running loop whose
    folder can be resolved), and unless `once` the key line. With `rows` (and not `once`) the view
    shrinks to leave the screen at most `rows - 1` lines; `color` adds the ANSI codes."""
    parts = [loops_list.report(ps_text, cwd_for, now, color)]
    budget = None if rows is None or once else rows - 4 - len(parts[0].splitlines())   # two blank lines, the key line, one spare
    shown = which or next((repo for _, repo in loops_ps.found_in(ps_text, cwd_for) if repo), None)
    if shown:
        if shown.isascii() and shown.isdigit():
            shown = os.path.join(".", shown)          # a folder named 3 is not loop number 3
        parts.append(project_view.view(shown, only, ps_text, cwd_for, now, budget, color)[1])
    if not once:
        parts.append(paint(KEYS.format(only or "all", refresh), "dim", color))
    return "\n\n".join(parts)
