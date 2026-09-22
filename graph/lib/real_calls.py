"""The two real providers, routed: which model and effort build or review a
card is `model_router.choose`'s call (docs/ROUTER.md), never a literal here.

Split out of `graph_commands.py` at the 200-line cap; that module still
imports both names, so `graph_commands._real_build` / `_real_review` and
`graph-goal.py`'s door stay put.
"""

from __future__ import annotations

import os
import pathlib

import model_router
import models
import resources
from backlog import Backlog
from campaign_of import backlog_of
from providers import BUILD_TIMEOUT, EFFORT, Outcome, claude, codex, codex_text

CLAUDE_BIN = os.environ.get("GRAPH_CLAUDE", "claude")
CODEX_BIN = os.environ.get("GRAPH_CODEX", "codex")


def _real_build(prompt, *, account, cwd, files, tools, denies, guard, effort="", resume="",
                model=""):
    """One builder call, in the task's own worktree, with the tools the task
    allows (lib/tools.py): a live task's builder has no shell, only the helper.
    `resume` continues the previous round's session — the same work, so what it
    already read is not paid for twice."""
    if models.builder_agent(model) == "codex":
        if guard:
            return Outcome("harness", text="guarded live builds require Claude")
        return codex_text(CODEX_BIN, prompt, model=model, effort=effort or EFFORT,
                          cwd=cwd, timeout=BUILD_TIMEOUT, write=True)
    return claude(CLAUDE_BIN, prompt, account=account, model=model, cwd=cwd, effort=effort,
                  resume=resume,
                  allowed_tools=tools, disallowed_tools=denies, guard=guard,
                  guard_files="\n".join(str(pathlib.Path(cwd) / f) for f in files) if guard else "")


def _real_review(prompt, *, cwd="", effort="", space=None, task_id=""):
    """A review from the router's own pick, walked through the same
    builder-independent belt it offered (docs/ROUTER.md). No candidate at all
    — every reviewer is the builder's own model — ends here, before any
    provider is asked, never a self-review.

    `cwd` is the worktree the diff or contract belongs to — never the
    driver's own checkout, or the reviewer reads the wrong tree. `space`/
    `task_id` default to nothing so a caller that only wants a verdict (a
    test, a one-off check) is not made to fake a workspace; the incoming
    `effort` is legacy and ignored — the route decides it now.
    """
    task = _routed_task(space, task_id)
    builder_model = task.get("builder_model") or resources.belt("build")[0].model
    try:
        choice = model_router.choose(task, "review", space=space, builder_model=builder_model)
    except LookupError as unavailable:
        return Outcome("harness", text=str(unavailable))
    belt = model_router.candidates("review", builder_model)
    ordered = [choice.resource] + [one for one in belt if one != choice.resource]
    walked = _walk(ordered)
    current = next(walked, None)

    def record(kind, account, cost, tokens, text):
        # `codex()`'s own `attempt` callback carries no model — a fixed arity
        # other callers already depend on — so which resource this outcome
        # actually belongs to is read from a walk mirroring its own belt
        # order and skip rule (`_walk`), never guessed from the account: the
        # routed event alone names only the preference, and a fallback that
        # walked past it needs its own actual settings on record
        # (docs/ROUTER.md: "Record ... actual call settings").
        nonlocal current
        resource = current
        space.attempt(task_id, account=account, kind=kind, cost=cost, tokens=tokens,
                      purpose="review")
        space.event("attempted_review", task=task_id, purpose="review", account=account,
                    outcome=kind, model=resource.model if resource else "", effort=choice.effort)
        try:
            current = walked.send(kind)
        except StopIteration:
            current = None
    return codex(CODEX_BIN, prompt, effort=choice.effort, cwd=cwd, belt=ordered,
                attempt=record if space is not None and task_id else None)


def _walk(ordered: list):
    """Which resource of `ordered` `codex()`'s own belt walk is asking next,
    mirrored from `resources.Exhausted` — the same skip rule it applies
    internally, fed the real outcome kind after each one so a later skip
    (an account exhausted by an earlier refusal) stays in step with it."""
    spent = resources.Exhausted()
    for resource in ordered:
        if spent.skip(resource):
            continue
        kind = yield resource
        spent.note(resource, kind)


def _routed_task(space, task_id: str) -> dict:
    """The full card the route is asked about, when one can be read — the
    router only needs its shape to describe the choice and to name its
    digest; a caller with no workspace (a test, a one-off check) gets a
    stub with just the id, and an unfiltered independence check still holds.
    """
    if space is None or not task_id:
        return {"id": task_id}
    path = backlog_of(space)
    found = Backlog(path).task(task_id) if path else None
    return found or {"id": task_id}
