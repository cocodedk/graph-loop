#!/usr/bin/env python3
"""loops — which lean loops are running on this machine, and what each is doing.

    loops.py
    loops.py <number or project folder> [--only built|open|attention]
    loops.py --screen [<project folder>] [--only ...] [--refresh <seconds>] [--once] [--rows <N>]
    loops.py --path <N>
    (any of the three prints with --color: the same text with ANSI codes; docs/lean/06-colours.md)

Prints the list, or one project's specs each with a mark, once; `--screen` prints both and the key
line, `--path` the folder of loop N. It only reads: no file is written and nothing is started.
Nothing needs it; a project that never uses it is not touched (docs/lean/02-loops-list.md,
docs/lean/03-project-view.md, docs/lean/04-live-screen.md; graph/loops.sh keeps the screen live).
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

sys.dont_write_bytecode = True   # it only reads: importing its modules must not leave .pyc files
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))   # lean_spec sits beside this file

import loops_list
import loops_ps


def main(argv: list[str] | None = None, read_ps=loops_ps.read_ps, cwd_of=loops_ps.cwd_of,
         clock=time.time) -> int:
    parser = argparse.ArgumentParser(prog="loops.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("which", nargs="?", help="a loop number from the list, or a project folder")
    parser.add_argument("--only", choices=("built", "open", "attention"), help="show only these specs")
    parser.add_argument("--screen", action="store_true", help="the list, a project view and the key line")
    parser.add_argument("--path", type=int, metavar="N", help="the project folder of loop N, or nothing")
    parser.add_argument("--refresh", default="15", help="the seconds the key line says")
    parser.add_argument("--once", action="store_true", help="with --screen: leave out the key line")
    parser.add_argument("--rows", type=int, help="with --screen: the terminal's height; the screen fits it")
    parser.add_argument("--color", action="store_true", help="add ANSI colour codes; without them the text is the same")
    args = parser.parse_args(argv)
    try:
        ps_text = read_ps()
    except loops_ps.PsError:
        print("cannot read the process list")
        return 1
    if args.which is None and not args.screen and args.path is None:
        print(loops_list.report(ps_text, cwd_of, clock(), args.color))
        return 0
    if args.path is not None or args.screen:
        import screen_view  # only the live screen needs it
        if args.path is not None:
            path = screen_view.folder(args.path, ps_text, cwd_of)
            if path:
                print(path)
            return 0
        print(screen_view.screen(args.which, args.only, args.refresh, args.once, ps_text, cwd_of, clock(), args.rows, args.color))
        return 0
    import project_view  # only a project view needs it
    code, text = project_view.view(args.which, args.only, ps_text, cwd_of, clock(), None, args.color)
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
