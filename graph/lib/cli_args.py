"""The command line of `graph-goal.py`, split out at the 200-line cap."""

from __future__ import annotations

import argparse

from lanes_auto import AUTO
from turn_plan import MOST_LANES


def lane_count(value: str):
    """`--lanes N` is a cap and stays one; `--lanes auto` hands the number to
    the throttler, which never returns more than the keeper's ceiling."""
    return AUTO if value.strip().lower() == AUTO else int(value)


def build_parser(description: str, commands: dict) -> argparse.ArgumentParser:
    """`commands` maps each subcommand name to the function that runs it."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--workspace", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("init"); start.add_argument("--backlog", required=True)
    start.add_argument("--goal", default=""); start.add_argument("--branch", default="")
    start.add_argument("--source", action="append", default=[],
                       help="approved source path the slicer may read; repeatable")
    start.set_defaults(run=commands["init"])

    src = sub.add_parser("sources")
    src.add_argument("--source", action="append", required=True,
                     help="approved repo-relative source path; repeatable")
    src.set_defaults(run=commands["sources"])
    for name in ("approve", "status", "report", "doctor"):
        sub.add_parser(name).set_defaults(run=commands[name])

    ahead = sub.add_parser("plan")
    ahead.add_argument("--rounds", type=int, default=0,
                       help="stop after this many slicer rounds; 0 runs until the "
                            "graph stops growing")
    ahead.set_defaults(run=commands["plan"])

    go = sub.add_parser("run")
    go.add_argument("--lanes", type=lane_count, default=MOST_LANES,
                    help="code cards run side by side, up to this many; a live card "
                         "always runs alone. `auto` lets the machine decide each "
                         "turn, under --lanes-max")
    go.add_argument("--lanes-max", type=int, default=0,
                    help="with --lanes auto: the owner's ceiling for this machine, "
                         "where it starts. Without one it starts at a single lane "
                         "and adds one per clean turn")
    go.add_argument("--max-tasks", type=int, default=0)
    go.add_argument("--dry-run", action="store_true")
    go.add_argument("--idle-seconds", type=int, default=300)
    go.add_argument("--hours-ceiling", type=float, default=2.0,
                    help="say so (once, as an alert) after this many hours since "
                         "progress — accepted work, a queued rebuild, or a passed "
                         "gate — and carry on")
    go.add_argument("--attempt-ceiling", type=int, default=12,
                    help="say so (once, as an alert) after this many answered "
                         "attempts since progress — accepted work, a queued "
                         "rebuild, or a passed gate — and carry on")
    go.set_defaults(run=commands["run"])

    halt = sub.add_parser("stop"); halt.add_argument("--now", action="store_true")
    halt.set_defaults(run=commands["stop"])
    return parser
