"""Shrinks a project view's spec lines to the lines it is given, and never cuts what needs a look."""

from __future__ import annotations

from collections.abc import Callable

from project_specs import BUILT, WAITING


def fit(rows: list[tuple[str, str]], line: Callable[[str, str], str], fixed: int, budget: int,
        extra: int) -> tuple[list[str], bool]:
    """The spec lines of `rows` (mark, name) for a view of `budget` lines whose other lines are `fixed`,
    and whether the `extra` lines (recently merged) still fit. The extra goes first, then the built
    specs become one line and the waiting ones give way, as many as fit; the rest stays."""
    room = budget - fixed
    if max(len(rows), 1) + extra <= room:
        return [line(*row) for row in rows], True
    if len(rows) <= room:
        return [line(*row) for row in rows], False
    built = sum(mark == BUILT for mark, _ in rows)
    waiting = [row for row in rows if row[0] == WAITING]
    left = room - (len(rows) - built - len(waiting)) - (built > 0)
    shown = waiting if len(waiting) <= left else waiting[:max(0, left - 1)]
    lines = [line(*row) for row in rows if row[0] not in (BUILT, WAITING)]
    if built:
        lines.append(line(BUILT, f"… {built} more"))
    lines += [line(*row) for row in shown]
    if len(waiting) > len(shown):
        lines.append(line(WAITING, f"… {len(waiting) - len(shown)} more"))
    return lines, False
