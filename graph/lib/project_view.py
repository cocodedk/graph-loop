"""One project's view: every spec with its mark, the loops running on it, and the filters."""

from __future__ import annotations

import collections
import os
from collections.abc import Callable

import lean_spec
import loops_alive
import loops_list
import loops_ps
import loops_step
import project_cost
import project_specs
from project_specs import BUILT, PR_OPEN, QUESTION, STOPPED

ONLY = {"built": lambda mark: mark == BUILT,
        "open": lambda mark: mark != BUILT,
        "attention": lambda mark: mark in (STOPPED, QUESTION, PR_OPEN)}
UNREADABLE = "git history unreadable: nothing is marked built"
WIDTH = max(len(mark) for mark in project_specs.MARKS)


def report(project: str, loops: list[loops_ps.Loop], now: float, only: str | None) -> str:
    """The text to print for `project`, whose running `loops` are given."""
    running = {lean_spec.slug(f"{loop.spec}.md") for loop in loops}
    found = project_specs.commits(project)
    built = project_specs.built_from(found)
    rows = [(project_specs.mark(path, running, built), lean_spec.slug(path.name))
            for path in project_specs.spec_files(project)]
    counts = collections.Counter(mark for mark, _ in rows)
    tally = " · ".join(f"{counts[mark]} {mark[2:]}" for mark in project_specs.MARKS if counts[mark])
    head = [f"{os.path.basename(project)}  {len(rows)} specs" + (f": {tally}" if tally else "")]
    turns, models = project_cost.card_turns(project), project_cost.card_models(project)
    for loop in loops:
        step, spent = loops_step.step(loop.workspace, loop.age, now)
        name = lean_spec.slug(f"{loop.spec}.md")
        using = " ".join(word for word in (loops_step.using(loop.workspace), f"{turns[name]}t" if name in turns else "") if word)
        alive = loops_alive.progress(loop.pid, now) if step == "building" else ""
        head.append(f"  loop: {name} {step} {loops_list.duration(spent)}" + "".join(f"  {part}" for part in (using, alive) if part))
    if built is None:
        head.append(UNREADABLE)
    costs = {name: f"${cost:.2f}" for name, cost in project_cost.card_costs(project).items()}
    named = max((len(name) for _, name in rows), default=0)
    dollars = max((len(cost) for cost in costs.values()), default=0)
    days = project_cost.card_days(project)

    def line(mark: str, name: str) -> str:
        if name not in costs:
            return f"{mark.ljust(WIDTH)}  {name}"
        extra = f"  {days[name]}" if name in days else ""
        extra += f"  {turns[name]}t" if name in turns else ""
        extra += f"  {models[name]}" if name in models else ""
        return f"{mark.ljust(WIDTH)}  {name.ljust(named)}  {costs[name].rjust(dollars)}{extra}"
    shown = [line(mark, name) for mark, name in rows if not only or ONLY[only](mark)]
    merged = project_specs.recent(found, {name for _, name in rows})
    tail = ["", "recently merged:", *(f"  {line}" for line in merged)] if merged else []
    return "\n".join([*head, "", *(shown or ["no specs match" if rows else "no specs"]), *tail])


def view(which: str, only: str | None, ps_text: str, cwd_for: Callable[[int], str | None],
         now: float) -> tuple[int, str]:
    """The exit status and text for a loop number or a project folder."""
    found = loops_ps.found_in(ps_text, cwd_for)
    shown = which
    if which.isascii() and which.isdigit():
        if not 1 <= int(which) <= len(found):
            return 2, f"no loop number {which}"
        project = shown = found[int(which) - 1][1] or "?"
    else:
        project = os.path.abspath(which)
    if not os.path.isdir(os.path.join(project, "docs", "lean")):
        return 2, f"not a project with docs/lean: {shown}"
    here = os.path.realpath(project)
    loops = [loop for loop, repo in found if repo and os.path.realpath(repo) == here]
    return 0, report(project, loops, now, only)
