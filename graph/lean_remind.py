#!/usr/bin/env python3
"""lean_remind — ring again when a project's lean loop is idle and a branch waits on the owner.

    lean_remind.py --repo <project folder> --workspace <its lean workspace>

Checks once and exits, for cron (for example every ten minutes, one entry per project). No lean loop running
for the project, and a branch on origin not merged (the set that stops the next run): it mails the owner
through the workspace's contact at 30 minutes, 4 hours and 24 hours after it first sees the same set, then
stays quiet until the set changes. It reads git and the process list and writes one file, `remind.json`,
in the workspace. Nothing needs it (graph/lib/lean_reminders.py has the rules).
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import time

sys.dont_write_bytecode = True   # a cron job must not leave .pyc files in the checkout
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import lean_git
import lean_reminders
import loops_ps
from workspace import Workspace


def main(argv: list[str] | None = None, read_ps=loops_ps.read_ps, unmerged=lean_git.unmerged,
         clock=time.time) -> int:
    parser = argparse.ArgumentParser(prog="lean_remind.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args(argv)
    try:
        ps_text = read_ps()
        print(lean_reminders.remind(args.repo, args.workspace, now=clock(), ps_text=ps_text,
                                    cwd_for=loops_ps.cwd_of, unmerged=unmerged,
                                    mail=Workspace(args.workspace).mail_person))
    except (loops_ps.PsError, subprocess.CalledProcessError, RuntimeError, OSError) as error:
        print(f"lean_remind: could not check ({error}); nothing sent")   # git or ps down: no state change
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
