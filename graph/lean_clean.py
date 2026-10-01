#!/usr/bin/env python3
"""lean_clean — remove the trees of specs that are merged.

    lean_clean.py --workspace <ws> --repo <project folder>

Runs leave their trees in the temp folder (a feature's checkout, the one its build ran in, the ones whose
removal failed), each in a folder of its own and each named in the workspace's event log by `task` and
`tree`. A tree goes only when its task is built on origin/main, never by age: a cleanup by age once deleted
a live run's tree. Only a tree in a folder the loop made (`graph-*`, `lean-build-*`) is touched. What cannot
be removed, files a container left owned by root, is printed as `left: <path>`.
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))

import project_specs
from workspace import Workspace

MADE = ("graph-", "lean-build-")   # the prefixes of the folders the loop makes its trees in


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lean_clean.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--repo", required=True)
    args = parser.parse_args(argv)
    built = project_specs.built_names(args.repo) or set()
    named = {row["tree"] for row in Workspace(args.workspace).events() if row.get("task") in built and row.get("tree")}
    for tree in sorted(named):
        folder = pathlib.Path(tree).parent
        if not folder.name.startswith(MADE) or not folder.exists():
            continue
        try:
            shutil.rmtree(folder)
            print(f"removed: {tree}")
        except OSError:
            print(f"left: {tree}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
