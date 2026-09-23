#!/usr/bin/env python3
"""lean — ship features, not proofs (docs/rfc/lean-loop.md, issue #124).

    lean.py --workspace <ws> --repo <repo> --spec <file> [--spec <file> ...] [--profile <file>]

Each spec file is one feature, run in the order given (`lean_run.py`); the run
stops at the first that does not land, since later specs build on it. The run
refuses to start without a proven contact (`graph-goal.py contact`), and
builds nothing while a reviewer reading the specs first has questions for
the person: they are emailed, and the run exits 2. The
profile, by default the `profile-*.md` the repository's CLAUDE.md links to,
gives three commands under `## suite_command`, `## build_command` and
`## artifact`, each an indented line. A run that merged anything ends by
building main and emailing the person that it is ready to accept.

This sits beside the current loop (`graph-goal.py`) and changes none of it.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))

import lean_git
import lean_run
from workspace import Workspace
from worktree import Worktree

FIELDS = ("suite_command", "build_command", "artifact")


def profile_path(repo: str, given: str = "") -> str:
    """`--profile`, or the profile the repository's CLAUDE.md links to."""
    if given:
        return str(pathlib.Path(given).resolve())
    guide = pathlib.Path(repo) / "CLAUDE.md"
    named = re.search(r"profile-[\w.-]*\.md", guide.read_text("utf-8")) if guide.exists() else None
    if not named or not (pathlib.Path(repo) / named.group(0)).is_file():
        raise SystemExit(f"no profile: {guide} links no profile-*.md here; pass --profile")
    return str(pathlib.Path(repo) / named.group(0))


def read_profile(path: str) -> dict:
    """The first indented line under each of the three headings."""
    values: dict = {}
    heading = ""
    for line in pathlib.Path(path).read_text("utf-8").splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
        elif heading in FIELDS and heading not in values and line[:1] in (" ", "\t") and line.strip():
            values[heading] = line.strip()
    missing = [field for field in FIELDS if field not in values]
    if missing:
        raise SystemExit(f"{path} has no indented line under: {', '.join('## ' + m for m in missing)}")
    return values


def finish(ws, repo: str, profile: dict, merged: list[str]) -> bool:
    """Build main in its own checkout and tell the person. The checkout stays:
    the artifact the email names lives in it."""
    tree = Worktree(repo, "build", commit=lean_git.MAIN).create(
        parent=tempfile.mkdtemp(prefix="lean-build-"))   # its own folder: the artifact lives here
    passed, tail = lean_run.masked(ws, profile["build_command"], tree.path)
    artifact = pathlib.Path(tree.path) / profile["artifact"]
    ready = passed and artifact.is_file()
    ws.event("lean_built", commit=tree.commit, passed=passed,
             artifact=str(artifact) if ready else "", tail=tail[-2000:])
    names = "\n".join(f"- {name}" for name in merged)
    if ready:
        lean_run.mail(ws, "graph-loop: ready to accept",
                      f"Merged to main, now at {tree.commit[:12]}:\n{names}\n\nThe build: {artifact}")
    else:
        why = "the build is red" if not passed else f"the build left no {profile['artifact']}"
        lean_run.mail(ws, "graph-loop needs you: the build on main",
                      f"Merged to main:\n{names}\n\nBut {why}:\n{tail}")
    return ready


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lean.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--spec", action="append", required=True, help="one feature; repeat, in order")
    parser.add_argument("--profile", default="")
    args = parser.parse_args(argv)
    ws = Workspace(args.workspace)
    ws.require_contact()                       # no proven channel, no run
    repo = str(pathlib.Path(args.repo).resolve())
    path = profile_path(repo, args.profile)
    profile = read_profile(path)
    specs = [str(pathlib.Path(spec).resolve()) for spec in args.spec]
    if lean_run.grill(ws, repo, specs, path):   # questions first: nothing is built on a guess
        return 2
    merged = []
    for spec in specs:         # in order: a later spec builds on the ones before it
        if not lean_run.run_feature(ws, repo, spec, profile, path):
            break
        merged.append(lean_run.slug(spec))
    if merged and not finish(ws, repo, profile, merged):
        return 1
    return 0 if len(merged) == len(args.spec) else 1


if __name__ == "__main__":
    sys.exit(main())
