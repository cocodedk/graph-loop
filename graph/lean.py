#!/usr/bin/env python3
"""lean — ship features, not proofs (docs/rfc/lean-loop.md, issue #124).

    lean.py --workspace <ws> --repo <repo> --spec <file> [--profile <file>]

One spec file per run is one feature (`lean_run.py`), and it becomes one pull
request: the branch `lean/<feature>`, built on origin's main. Nothing is ever
landed on main, and nothing is built while any branch on origin is unmerged,
the loop's own or a person's: the person is emailed the list and the run exits 3.
One exception: when the only unmerged branch is this spec's own open pull request
and it has unresolved review threads, the run fixes those on that branch and
pushes to the same pull request.
The run also refuses to start without a proven contact (`graph-goal.py
contact`), and builds nothing while a reviewer reading the spec first has
questions for the person: they are emailed, and the run exits 2. The profile,
by default the `profile-*.md` the repository's CLAUDE.md links to, gives three
commands under `## suite_command`, `## build_command` and `## artifact`, each an
indented line. A run that opened a pull request ends by building that branch
and emailing the person that it is ready for review.

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
import lean_spec
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


def finish(ws, repo: str, profile: dict, feature: str, url: str) -> bool:
    """Build the feature's branch in its own checkout and tell the person. The
    checkout stays: the artifact the email names lives in it."""
    tree = Worktree(repo, "build", commit=f"refs/heads/lean/{feature}").create(
        parent=tempfile.mkdtemp(prefix="lean-build-"))   # its own folder: the artifact lives here
    passed, tail = lean_run.masked(ws, profile["build_command"], tree.path)
    artifact = pathlib.Path(tree.path) / profile["artifact"]
    ready = passed and artifact.is_file()
    ws.event("lean_built", commit=tree.commit, passed=passed,
             artifact=str(artifact) if ready else "", tail=tail[-2000:])
    if ready:
        lean_run.mail(ws, "graph-loop: ready for review",
                      f"{feature}: {url}\n\nThe build: {artifact}\n\nReview and merge the pull "
                      "request; the next spec waits until it is merged.")
    else:
        why = "the build is red" if not passed else f"the build left no {profile['artifact']}"
        lean_run.mail(ws, f"graph-loop needs you: the build of {feature}",
                      f"{feature}: {url}\n\nBut {why}:\n{tail}")
    return ready


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lean.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--spec", action="append", required=True,
                        help="one feature: its pull request is merged before the next run")
    parser.add_argument("--profile", default="")
    args = parser.parse_args(argv)
    if len(args.spec) != 1:
        parser.error("one spec per run: the next is built once this one's pull request is merged")
    ws = Workspace(args.workspace)
    ws.require_contact()                       # no proven channel, no run
    repo = str(pathlib.Path(args.repo).resolve())
    try:
        path = profile_path(repo, args.profile)
    except SystemExit as missing:            # the person chooses the profile, told how
        shelf = pathlib.Path(__file__).resolve().parents[1] / "profiles"
        names = "\n".join(f"- {kind.name}" for kind in sorted(shelf.glob("*.md")))
        lean_run.mail(ws, "graph-loop needs a profile",
                      f"{missing}\n\nCopy one of these from {shelf} into the repository as "
                      f"profile-<name>.md and link it from CLAUDE.md:\n{names}")
        raise
    profile = read_profile(path)
    spec = str(pathlib.Path(args.spec[0]).resolve())
    info = lean_spec.front(pathlib.Path(spec).read_text("utf-8"))
    waiting, revise = lean_git.unmerged(repo), ""
    own = waiting == [f"origin/lean/{lean_run.slug(spec)}"] and info.get("lean_status") == "pr_open"
    if own:                                    # its own pull request: fix what review found
        revise = lean_git.threads(str(info.get("lean_pr", "")))
    if waiting and not revise:                 # nothing starts from main while anything waits
        ws.event("lean_waiting", branches=waiting)
        names = "\n".join(f"- {name}" for name in waiting)
        lean_run.mail(ws, "graph-loop is waiting: unmerged branches",
                      f"Nothing was built. Merge or delete these branches first:\n{names}"
                      + ("\n\nIts own pull request has no unresolved review threads to fix." if own else ""))
        return 3
    if not revise and lean_run.grill(ws, repo, [spec], path):   # questions first: nothing on a guess
        return 2
    url = lean_run.run_feature(ws, repo, spec, profile, path, revise, str(info.get("lean_pr", "")))
    if not url:
        return 1
    return 0 if finish(ws, repo, profile, lean_run.slug(spec), url) else 1


if __name__ == "__main__":
    sys.exit(main())
