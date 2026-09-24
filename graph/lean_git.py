"""The lean loop's git moves: refuse while anything is unmerged, commit a finished
worktree, and publish it as a pull request.

A builder's worktree refuses every ref write (`lib/hooks/reference-transaction`),
so the commit is built from the repository's side, as `keep.py` does: a private
index over the worktree's files, written into the repository's own object store.
Nothing is ever moved onto main. Each feature is pushed as a new branch,
`lean/<feature>`, with a pull request the person reviews and merges; until every
branch on origin is merged, the loop builds nothing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

BASE = "refs/remotes/origin/main"   # every feature starts here, after a fetch


def git(cwd: str, *args: str, env: dict | None = None) -> str:
    done = subprocess.run(("git", *args), cwd=cwd, capture_output=True, text=True, check=False,
                          env={**os.environ, **env} if env else None)
    if done.returncode:
        raise RuntimeError(f"git {' '.join(args[:3])}: {(done.stderr or done.stdout).strip()[:300]}")
    return done.stdout.strip()


def commit(repo: str, tree: str, base: str, subject: str) -> str:
    """The worktree's files as one commit on `base`, in the repository's store."""
    gitdir = git(repo, "rev-parse", "--absolute-git-dir")
    scratch = tempfile.mkdtemp(prefix="lean-index-")
    env = {"GIT_INDEX_FILE": os.path.join(scratch, "index")}   # not there yet: git makes it
    where = ("--git-dir", gitdir, "--work-tree", tree)
    try:
        git(tree, *where, "read-tree", base, env=env)
        git(tree, *where, "add", "-A", env=env)
        written = git(tree, *where, "write-tree", env=env)
        return git(repo, "commit-tree", written, "-p", base, "-m", subject)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def unmerged(repo: str) -> list[str]:
    """Every branch on origin not merged into its main, after a fetch: the loop's own
    unreviewed work and a person's alike. While any is listed, nothing is built."""
    git(repo, "fetch", "--quiet", "--prune", "origin")
    listed = git(repo, "for-each-ref", "--format=%(refname:short)", "--no-merged", BASE,
                 "refs/remotes/origin")
    return [name for name in listed.splitlines() if name not in ("origin", "origin/HEAD")]


def publish(repo: str, work: str, feature: str, title: str, body: str) -> str:
    """Push commit `work` as the new branch lean/<feature>; its pull request's URL."""
    branch = f"lean/{feature}"
    git(repo, "update-ref", f"refs/heads/{branch}", work, "")   # new only: never moves a branch
    git(repo, "push", "--quiet", "origin", f"refs/heads/{branch}:refs/heads/{branch}")
    return pull_request(repo, branch, title, body)


def pull_request(repo: str, branch: str, title: str, body: str) -> str:
    done = subprocess.run(("gh", "pr", "create", "--base", "main", "--head", branch,
                           "--title", title, "--body", body), cwd=repo, capture_output=True,
                          text=True, check=False)
    if done.returncode:
        raise RuntimeError(f"gh pr create: {(done.stderr or done.stdout).strip()[:300]}")
    return done.stdout.strip().splitlines()[-1]
