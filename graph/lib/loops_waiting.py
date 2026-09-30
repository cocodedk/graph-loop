"""The block of the list for the recorded projects that wait for a person and have no loop running."""

from __future__ import annotations

import os

import loops_ps
from screen_color import paint

HEADING = "waiting for you:"


def rows(found: list[tuple[loops_ps.Loop, str | None]], recorded: list[str]) -> list[tuple[str, str, str, str]]:
    """The (project, spec, mark, colour) of each spec that needs a person, for the recorded folders without a
    running loop (`found`, by --repo), in folder-name and spec order. The specs are read only when a folder is recorded."""
    if not recorded:
        return []
    import waiting_view  # needs the specs' modules: a list with nothing recorded stays free of them
    running = {os.path.realpath(repo) for _, repo in found if repo}
    folders = sorted({os.path.realpath(folder) for folder in recorded} - running,
                     key=lambda folder: (os.path.basename(folder), folder))
    return [(os.path.basename(folder), spec, mark, style) for folder in folders
            for spec, mark, style in waiting_view.specs_of(folder)]


def lines(waiting: list[tuple[str, str, str, str]], widths: list[int], color: bool = False) -> list[str]:
    """The heading and one line for each row, its project and spec in the columns `widths` gives (number,
    project, spec) so they sit under the loop lines' columns; nothing when there are no rows."""
    if not waiting:
        return []
    return [paint(HEADING, "bold", color), *(
        " " * widths[0] + paint(project.ljust(widths[1]) + spec.ljust(widths[2]) + mark[2:], style, color)
        for project, spec, mark, style in waiting)]
