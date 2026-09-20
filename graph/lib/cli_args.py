"""The command line of `graph-goal.py`, split out at the 200-line cap."""

from __future__ import annotations

import argparse


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
    for name in ("approve", "status", "report", "doctor", "remember"):
        sub.add_parser(name).set_defaults(run=commands[name])

    ahead = sub.add_parser("plan")
    ahead.add_argument("--rounds", type=int, default=0,
                       help="stop after this many slicer rounds; 0 runs until the "
                            "graph stops growing")
    ahead.set_defaults(run=commands["plan"])

    go = sub.add_parser("run")
    go.add_argument("--lanes", type=int, default=3,
                    help="code cards run side by side; a live card always runs alone")
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
