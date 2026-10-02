#!/usr/bin/env python3
"""graph-goal — prove the workspace can reach its person.

    graph-goal.py --workspace <ws> contact "<email-address>"

Sends a test mail to the address and records it in the workspace. `lean.py`
refuses to run without that record. The campaign driver that once lived here
was removed on 2026-10-02; the lean loop (`lean.py`) is the loop.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))

import alert_email
import durable
from workspace import Workspace
from workspace_repo import project


def command_contact(args) -> int:
    space = Workspace(args.workspace)
    channel = args.channel.strip()
    if not channel:
        raise SystemExit("contact requires an email address")
    alert_email.send("Campaign contact test", "This campaign can now reach its person.",
                     subject=f"[{project(space)}] graph-loop: can this campaign reach you?",
                     recipient=channel)
    with space.only_writer():
        durable.replace(space.root / "contact", channel + "\n")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="graph-goal.py", description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    contact = commands.add_parser("contact")
    contact.add_argument("channel")
    contact.set_defaults(run=command_contact)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
