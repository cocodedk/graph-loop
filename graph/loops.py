#!/usr/bin/env python3
"""loops — which lean loops are running on this machine, and what each is doing.

    loops.py

Prints the list once. It only reads: no file is written and nothing is started.
Nothing needs it; a project that never uses it is not touched (docs/lean/02-loops-list.md).
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

sys.dont_write_bytecode = True   # it only reads: importing its modules must not leave .pyc files
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))

import loops_list
import loops_ps


def main(argv: list[str] | None = None, read_ps=loops_ps.read_ps, cwd_of=loops_ps.cwd_of,
         clock=time.time) -> int:
    argparse.ArgumentParser(prog="loops.py", description=__doc__.split("\n\n")[0]).parse_args(argv)
    try:
        ps_text = read_ps()
    except loops_ps.PsError:
        print("cannot read the process list")
        return 1
    print(loops_list.report(ps_text, cwd_of, clock()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
