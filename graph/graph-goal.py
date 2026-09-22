#!/usr/bin/env python3
"""graph-goal — work a backlog to done, and say so when it cannot.

    graph-goal.py init --backlog <file> [--goal "..."] [--branch <name>] [--source <path>]...
    graph-goal.py approve
    graph-goal.py plan [--rounds N]
    graph-goal.py run [--lanes 3|auto [--lanes-max N]] [--max-tasks N] [--dry-run]
    graph-goal.py status
    graph-goal.py report
    graph-goal.py remember
    graph-goal.py doctor
    graph-goal.py stop [--now]
    graph-goal.py cuts [--state off|observe|act --by <name>]

`plan` and building never overlap: `plan` writes every card the slicer can cut
and builds nothing. When `run` has nothing startable and nobody building, it
runs the same plan phase before standing down. A card that fails a build parks
and is re-sliced against the code as it then stands.

The campaign lives in `graph/campaign/` unless `--workspace` says
otherwise: an append-only record of everything the loop did, the claims of what
is running, and the stop flag it reads between tasks.
"""

from __future__ import annotations

import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))

import where
from backlog import Backlog
from campaign_of import branch_of
from cli_args import build_parser
from cuts_command import command_cuts
from doctor_auth import run_accounts
from driver_turn import after_lanes, before_turn, rollup_nodes
from finishing import ENDED_WITH_GAPS, stand_down
from loop import Loop
from loop_environment import environment_stop
from plan_phase import plan
from remember import command_remember  # a hand-run command, never a step of the loop
from throttle import Throttle
from turn_plan import code_first, width_against_lanes
from workspace_claims import _now, _started
from workspace_repo import alert_cwd

HERE = pathlib.Path(__file__).resolve().parent

# The log is the product of a campaign: it lives in the repository's scratchpad,
# gets committed, and is never thrown away (the owner, 2026-08-28: "these logs are
# worth gold"). Rotation keeps each part small enough to read. `where` answers
# which repository and campaign — override with GRAPH_REPO / GRAPH_CAMPAIGN /
# GRAPH_BACKLOG / GRAPH_BRANCH to point the loop at other work.
from graph_commands import (
    _backlog_of,
    _real_build,
    _real_review,
    _space,
    command_approve,
    command_doctor,
    command_init,
    command_plan,
    command_report,
    command_sources,
    command_status,
    command_stop,
    run_lanes,
    stood_down,
    taking_now,
    turn_opens,
)


def command_run(args) -> int:
    space = _space(args)
    if not (space.root / "approved").exists():
        raise SystemExit("not approved — run `graph-goal.py approve` first")
    if not args.dry_run:   # only a driver claims the campaign; a dry run writes nothing
        space.only_driver()
        space.event("driver_started", pid=os.getpid(), started=_started(os.getpid()))
        with run_accounts(space) as remaining:
            if not remaining:
                return stood_down(space, 1, "no account can sign in")
            return _run(args, space)
    return _run(args, space)


def _run(args, space) -> int:
    repo = where.repo(space, persist=not args.dry_run)
    if not args.dry_run:
        alert_cwd(space, repo)
    book = Backlog(_backlog_of(space))
    loop = Loop(repo=str(repo), backlog=book, space=space,
                build=_real_build, review=_real_review,
                branch=branch_of(space))   # the campaign's own reading, shared with the handoff
    started = 0
    started_at = space.code_digest()   # what the code IS, so a touched mtime is not a change
    # `--lanes auto` only: with a number, and in a dry run, this does nothing
    # at all — no reading of the machine, no file, no event.
    throttle = Throttle(space, args)
    while True:
        before_turn(loop, book, space, args)   # recover a decision, then reconcile
        ending = turn_opens(space, book, args, started_at, started)
        if ending is not None:
            return ending if isinstance(ending, int) else 0
        running = list(space.running())
        ready = book.startable(running=running)
        if not ready:
            left = [row["id"] for row in book.unfinished()]
            print(f"{_now()} " + (f"nothing to start; unfinished: {left or 'none'}").replace("\n", f"\n{_now()} "), flush=True)
            if args.dry_run:
                break        # a dry run says what it would do; a stand-down WRITES
            if not left or not running:
                if not running:
                    plan(book, space)
                    if book.startable():
                        continue
                    left = [row["id"] for row in book.unfinished()]
                code = stand_down(space, book)   # 0 only when the campaign is really finished
                return stood_down(space, code, f"nothing startable; unfinished: {left or 'none'}")
            # Another agent holds a claim, and finishing it can release a
            # dependency of one of these: the loop waits rather than ending the
            # weekend early.
            space.event("idle", unfinished=left, running=running, sleep=args.idle_seconds)
            space.idle(args.idle_seconds)
            continue
        chosen = throttle.lanes(len(code_first(ready)))
        taking = taking_now(ready, args, started, chosen)
        if args.dry_run:
            for row in taking:
                print(f"{_now()} " + (f"would run {row['id']}: {row['goal']}").replace("\n", f"\n{_now()} "), flush=True)
            break
        turn_id = f"turn-{started}-{int(time.time())}"
        # What the graph offered against what the loop could run, before it
        # runs: a turn that dies still says how wide its frontier was.
        width_against_lanes(space, ready, taking, args, turn_id, chosen)
        throttle.opens()      # the baseline, read with no lane running
        try:
            ran, outside = run_lanes(loop, book, space, taking, turn_id=turn_id)
        finally:
            throttle.closes(turn_id, len(taking))
            rollup_nodes(book, space)
        started += ran
        if why := environment_stop(space):
            return stood_down(space, ENDED_WITH_GAPS, why)
        # The doctor and the watchdog read what this turn just did, and write
        # what they find into the log nobody is here to read (lib/driver_turn.py).
        after_lanes(book, space, args, taking)
        if args.max_tasks and started >= args.max_tasks:
            print(f"{_now()} " + (f"reached --max-tasks {args.max_tasks}").replace("\n", f"\n{_now()} "), flush=True)
            stood_down(space, 0, f"reached --max-tasks {args.max_tasks}")
            break
        if outside:
            # A usage limit, an expired account, a provider down: it resets
            # without anybody doing anything, so the loop waits for it. This is
            # the one thing the driver waits on, and it never waits on a person.
            print(f"{_now()} " + "  the fault is outside the tasks", flush=True)
            space.alert("the campaign", f"the fault is outside the tasks; cooling down for "
                        f"{args.idle_seconds} seconds before retrying")
            space.event("pause", tasks=[row["id"] for row in taking], sleep=args.idle_seconds)
            space.idle(args.idle_seconds)
    return 0


def main(argv=None) -> int:
    parser = build_parser(__doc__.splitlines()[0], {
        "init": command_init, "sources": command_sources,
        "approve": command_approve, "status": command_status,
        "report": command_report, "doctor": command_doctor,
        "remember": command_remember, "cuts": command_cuts,
        "plan": command_plan, "run": command_run, "stop": command_stop})
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
