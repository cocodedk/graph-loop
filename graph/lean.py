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
contact`), and builds nothing while a reviewer reading the spec before its first
build has questions for the person: they are emailed, and the run exits 2. The profile,
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

import accounts
import lean_git
import lean_run
import lean_spec
import projects_log
from workspace import Workspace
from worktree import Worktree

FIELDS = ("suite_command", "build_command", "artifact")
OPTIONAL = ("account", "lint_command")   # `account`: the one login the project spends, by the name GRAPH_ACCOUNTS gives it


def profile_path(repo: str, given: str = "") -> str:
    """`--profile`, or the profile the repository's CLAUDE.md links to."""
    if given:
        return str(pathlib.Path(given).resolve())
    guide = pathlib.Path(repo) / "CLAUDE.md"
    named = re.search(r"profile-[\w.-]*\.md", guide.read_text("utf-8")) if guide.exists() else None
    if not named or not (pathlib.Path(repo) / named.group(0)).is_file():
        raise SystemExit(f"Link a profile-*.md from {guide}, or pass --profile: it links none.")
    return str(pathlib.Path(repo) / named.group(0))


def read_profile(path: str) -> dict:
    """The first indented line under each of the three headings, and under `## account` and `## lint_command` if any."""
    values: dict = {}
    heading = ""
    for line in pathlib.Path(path).read_text("utf-8").splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
        elif heading in FIELDS + OPTIONAL and heading not in values and line[:1] in (" ", "\t") and line.strip():
            values[heading] = line.strip()
    missing = [field for field in FIELDS if field not in values]
    if missing:
        raise SystemExit(f"Add an indented line under each of these headings in {path}: {', '.join('## ' + m for m in missing)}")
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
        fix = "Fix the red build" if not passed else f"Make the build leave {profile['artifact']}"
        lean_run.mail(ws, f"graph-loop needs you: the build of {feature}",
                      f"{feature}: {url}\n\nThe pull request is open. {fix}:\n{tail}")
    return ready


def end(code: int, words: str) -> int:
    """The run's last line, so a log that holds only the mail's line still says how it ended."""
    print(f"lean: exit {code}, {words}")
    return code


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
    projects_log.record(args.repo)             # so the dashboard still lists it once the loop has exited
    ws = Workspace(args.workspace)
    ws.require_contact()                     # no proven channel, no run
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
    try:
        accounts.restrict(profile.get("account", ""))
    except SystemExit as unknown:            # never another account's login: told what to add
        lean_run.mail(ws, "graph-loop needs the project's account", str(unknown))
        raise
    spec = str(pathlib.Path(args.spec[0]).resolve())
    info = lean_spec.front(pathlib.Path(spec).read_text("utf-8"))
    try:
        waiting, revise = lean_git.unmerged(repo), ""
    except RuntimeError as error:              # every try failed: nothing was built, and the person is told what to do
        ws.event("lean_fetch_failed", error=str(error)[:500])
        lean_run.mail(ws, "graph-loop needs you: git fetch failed",
                      f"Run the spec again once `git fetch origin` works in {repo}. Nothing was built.\n\n{error}")
        return end(1, "git fetch failed, nothing was built")
    own = waiting == [f"origin/lean/{lean_run.slug(spec)}"] and info.get("lean_status") == "pr_open"
    if own:                                    # its own pull request: fix what review found
        revise = lean_git.threads(str(info.get("lean_pr", "")))
    if waiting and not revise:                 # nothing starts from main while anything waits
        ws.event("lean_waiting", branches=waiting)
        names = "\n".join(f"- {name}" for name in waiting)
        lean_run.mail(ws, "graph-loop is waiting: unmerged branches",
                      f"Nothing was built. Merge or delete these branches first:\n{names}"
                      + ("\n\nIts own pull request has no unresolved review threads to fix." if own else ""))
        return end(3, "waiting on unmerged branches, nothing was built")
    # Questions first, nothing on a guess: once, before a spec's first build. A spec
    # carrying on after a stop was grilled then. The status does not prove the text is
    # unchanged: a spec whose requirements change starts afresh without its lean_ fields.
    open_questions = ""
    if not revise and info.get("lean_status") != "stopped":
        count = lean_spec.rounds(info)
        asked = lean_run.grill(ws, repo, [spec], path, earlier=str(info.get("lean_asked") or ""),
                               final=count + 1 >= lean_spec.GRILL_ROUNDS)
        if asked:                                  # kept, so nothing takes it for a spec that only waits
            real = lean_spec.refused(ws.events())  # a failure to answer is no round, and lets nothing through
            count += real
            lean_spec.record(spec, lean_status="questions", lean_rounds=count, lean_asked=asked if len(asked) <= lean_spec.ASKED_LIMIT
                             else asked[:lean_spec.ASKED_LIMIT] + lean_spec.CUT_NOTE)
            if not (real and count >= lean_spec.GRILL_ROUNDS):
                return end(2, "questions, nothing was built")
            open_questions = asked                 # the round limit: this run goes on with them
    url = lean_run.run_feature(ws, repo, spec, profile, path, revise, str(info.get("lean_pr", "")),
                               open_questions=open_questions)
    if not url:
        return end(1, "stopped, see the mail and events.jsonl")
    if finish(ws, repo, profile, lean_run.slug(spec), url):
        return end(0, f"pr_open {url}")
    return end(1, f"pr_open {url}, but the build is not ready")


if __name__ == "__main__":
    sys.exit(main())
