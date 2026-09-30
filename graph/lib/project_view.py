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
import project_fit
import project_specs
from project_specs import BUILT, MARK_STYLE, PR_OPEN, QUESTION, STOPPED
from screen_color import costly, paint

ONLY = {"built": lambda mark: mark == BUILT,
        "open": lambda mark: mark != BUILT,
        "attention": lambda mark: mark in (STOPPED, QUESTION, PR_OPEN)}
UNREADABLE = "git history unreadable: nothing is marked built"
WIDTH = max(len(mark) for mark in project_specs.MARKS)
SLOW_STEPS = ("testing", "checking the build")   # the log is quiet while these run: 15 minutes is red


def report(project: str, loops: list[loops_ps.Loop], now: float, only: str | None,
           budget: int | None = None, color: bool = False) -> str:
    """The text to print for `project`, whose running `loops` are given; `color` adds the ANSI codes
    of docs/lean/06-colours.md and nothing else."""
    running = {lean_spec.slug(f"{loop.spec}.md") for loop in loops}
    found = project_specs.commits(project)
    built = project_specs.built_from(found)
    rows = [(project_specs.mark(path, running, built), lean_spec.slug(path.name))
            for path in project_specs.spec_files(project)]
    counts = collections.Counter(mark for mark, _ in rows)
    tally = " · ".join(f"{counts[mark]} {mark[2:]}" for mark in project_specs.MARKS if counts[mark])
    head = [paint(f"{os.path.basename(project)}  {len(rows)} specs" + (f": {tally}" if tally else ""), "bold", color)]
    turns, models = project_cost.card_turns(project), project_cost.card_models(project)
    for loop in loops:
        step, spent = loops_step.step(loop.workspace, loop.age, now)
        name = lean_spec.slug(f"{loop.spec}.md")
        using = " ".join(word for word in (loops_step.using(loop.workspace), f"{turns[name]}t" if name in turns else "") if word)
        alive = loops_alive.progress(loop.pid, now, color=color) if step == "building" else ""
        late = "red" if step in SLOW_STEPS and spent >= 900 else ""
        head.append(f"{paint(f'  loop: {name}', 'bold', color)} {paint(f'{step} {loops_list.duration(spent)}', late, color)}"
                    + "".join(f"  {part}" for part in (using, alive) if part))
    if built is None:
        head.append(UNREADABLE)
    prices = project_cost.card_costs(project)
    costs = {name: f"${cost:.2f}" for name, cost in prices.items()}
    named = max((len(name) for _, name in rows), default=0)
    wide = max((len(cost) for cost in costs.values()), default=0)
    days = project_cost.card_days(project)

    def line(mark: str, name: str) -> str:
        """A spec's line, padded plain and painted after. A waiting line is dim whole and a shrink line
        (`… N more`) has its mark's colour whole; the others colour the mark, the cost and the extras."""
        style = MARK_STYLE[mark]
        whole = style == "dim" or name.startswith("…")

        def part(text: str, tint: str) -> str:
            return text if whole else paint(text, tint, color)
        rest = f"  {name}"
        if name in costs:
            extras = (days.get(name), f"{turns[name]}t" if name in turns else "", models.get(name))
            rest = (f"  {name.ljust(named)}  {' ' * (wide - len(costs[name]))}{part(costs[name], costly(prices[name]))}"
                    + "".join(f"  {part(text, 'dim')}" for text in extras if text))
        text = f"{part(mark, style)}{' ' * (WIDTH - len(mark))}{rest}"
        return paint(text, style, color) if whole else text
    wanted = [(mark, name) for mark, name in rows if not only or ONLY[only](mark)]
    merged = project_specs.recent(found, {name for _, name in rows})
    tail = ["", paint("recently merged:", "bold", color), *(paint(f"  {text}", "dim", color) for text in merged)] if merged else []
    shown, keep = [line(mark, name) for mark, name in wanted], True
    if budget is not None:
        shown, keep = project_fit.fit(wanted, line, len(head) + 1, budget, len(tail))
    return "\n".join([*head, "", *(shown or ["no specs match" if rows else "no specs"]), *(tail if keep else [])])


def view(which: str, only: str | None, ps_text: str, cwd_for: Callable[[int], str | None],
         now: float, budget: int | None = None, color: bool = False) -> tuple[int, str]:
    """The exit status and text for a loop number or a project folder; `budget` is the most lines the
    text may take (see project_fit), `color` adds the ANSI codes."""
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
    return 0, report(project, loops, now, only, budget, color)
