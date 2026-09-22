"""One turn of the driver: what it decides before it picks work, which cards
it rewrites, and how it runs the lanes.

Split out of `graph_commands` at the 200-line cap. A live card runs alone (it
acts on one shared stack); code cards run side by side, each in its own
worktree, with one writer at a time on the task list.

**A turn does not plan.** The slicer used to run at the top of every one of
them, which is the plan phase and the build phase mixed by construction. The
planning is `lib/plan_phase.py` now, run on its own with the driver stopped;
what is left here is the two flags, the loop's own code, one refused contract
rewritten, and the lanes.
"""

from __future__ import annotations

import os

import resources
from backlog_decision import can_replan
from issue_drafts import draft_stalls
from lanes import run_lanes  # noqa: F401 — run_lanes' front door stays here
from providers import PLAN_TIMEOUT, claude
from replan import replan_until_planned
from replan_budget import alert_stopped
from triage import triage_pending
from triage_paths import contract_path
from turn_plan import taking_now  # noqa: F401 — the driver's door
from workspace_flags import RESTART_EXIT


def stood_down(space, code: int, why: str) -> int:
    """Say in the campaign's own record why this driver is ending, and with
    what exit. The record held `driver_started` and nothing at the other end,
    so a campaign that stopped by itself could not be asked why: six of them
    were restarted by hand and the log said only that a driver had begun
    (2026-09-18). Exit 75 in particular is not a failure — it asks the
    supervisor for a new driver — and read from outside it looks like a stop.
    """
    space.event("driver_stood_down", why=why, exit=code,
                supervisor_restarts=code == RESTART_EXIT)
    draft_stalls(space)
    return code

CLAUDE_BIN = os.environ.get("GRAPH_CLAUDE", "claude")


def plan_with_claude(prompt: str, resource=None):
    """One planner call on one resource: no tools, and a planner's own, shorter
    timeout. The caller walks the belt, so every call leaves its own record."""
    resource = resource or resources.belt("plan")[0]
    return claude(CLAUDE_BIN, prompt, account=resource.account, model=resource.model,
                  no_tools=True, timeout=PLAN_TIMEOUT)


def replan_pending(book, space, planner=None) -> bool:
    """Refused contracts with rounds left are rewritten at the top of a turn,
    one per turn: the reviewer's findings become the next contract, and a
    planner no resource reached (a limit, capacity, an expired session) is
    asked again next turn instead of stranding the task. A call that was paid
    for and did not finish spends its round like any other answered refusal.
    A rejected diff is not a contract problem and never comes here."""
    planner = planner or plan_with_claude
    for task in book.tasks():
        # `backlog_decision.can_replan` is this condition's one home, so the
        # plan phase and this path cannot both claim the same card.
        if not can_replan(task):
            alert_stopped(book, space, task)
            continue
        if contract_path(book, space, task):
            return True
        def recorded(prompt: str, task_id: str = task["id"]):
            """Every planner call leaves its own record: a summary of the last
            one hid what the first cost and what it answered.

            The accounts are walked here, not inside the call, so a session that
            expires on one leaves a record of its own rather than vanishing into
            the answer of the next. The attempt is filed under `plan` whichever
            account answered, because a planner call rewrites a contract and
            builds nothing to keep (`doctor.check_costly_silence`); the account
            that actually ran is on the call's own step."""
            space.artifact(task_id, "replan-prompt", prompt)
            out, spent = None, resources.Exhausted()
            for resource in resources.belt("plan"):
                if spent.skip(resource):
                    continue      # this account or this model has already said no
                with space.step(task_id, "replan_call") as call:
                    out = planner(prompt, resource)
                    call(outcome=out.kind, cost=out.cost, tokens=out.tokens, on=str(resource))
                space.artifact(task_id, "replan-answer", out.raw or out.text)
                space.attempt(task_id, account="plan", kind=out.kind, cost=out.cost,
                              tokens=out.tokens)
                if getattr(out, "ok", False) or not resources.refused_before_reading(out.kind):
                    break
                spent.note(resource, out.kind)
            return out

        # `replan_call` above already times the one real unit of work — one
        # planner call on one resource, the same granularity as every other
        # named step in this loop (contract, gate, build, ...). Wrapping it in
        # a second, wider "replan" step nested one span inside the other, so
        # report.py's clock, by_step and by_task totals summed the same
        # seconds twice. The outcome is still recorded once, below, as a
        # plain event rather than a second step.
        fixed = replan_until_planned(book, task, recorded, space=space)
        print(f"  replan {task['id']}: {fixed.why[:160]}")
        space.event("replanned" if fixed.rewritten else "replan_refused", task=task["id"], why=fixed.why[:300])
        return True
    return False


def turn_opens(space, book, args, started_at: str, started: int = 0):
    """What a turn decides before it picks a task: the two flags, the loop's own
    code, and one refused contract rewritten — and no planning of any kind. Returns None to carry on, an exit
    code to stand down, or 0 when a stop was asked for. `started` is how many
    cards this driver has run, which `--max-tasks` counts against.

    `started_at` is the digest of the loop's code this driver started on.
    """
    if not args.dry_run:
        triage_pending(book, space)
    flag = "" if args.dry_run else space.stop_or_restart()
    if not flag and not args.dry_run and space.code_changed(started_at):
        # No flag, no person: the code changed under this driver, so it stands
        # down between tasks and the supervisor starts one on the new code.
        print("the loop's code changed — restarting on it")
        return stood_down(space, RESTART_EXIT, "the loop's code changed under this driver")
    if not flag and not args.dry_run:
        # One refused contract rewritten, and nothing else. A turn does not
        # PLAN: the slicer that used to run at the top of every one of them
        # belongs to the plan phase now (`lib/plan_phase.py`).
        replan_pending(book, space)
        flag = space.stop_or_restart()   # a flag raised during the planner call is not crossed
    if flag == "stop":
        print("stop requested — leaving the rest of the backlog untouched")
        return stood_down(space, 0, "a person asked it to stop")
    if flag == "restart":
        print("restart requested — the supervisor starts the next driver")
        return stood_down(space, RESTART_EXIT, "a person asked for a restart")
    return None
