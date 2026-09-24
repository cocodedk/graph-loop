"""The lean loop's two git moves: commit a finished worktree, and land it on the campaign branch.

A builder's worktree refuses every ref write (`lib/hooks/reference-transaction`),
so the commit is built from the repository's side, as `keep.py` does: a private
index over the worktree's files, written into the repository's own object store.
The branch is then moved forward, never forced: by `merge --ff-only` in the checkout
that holds it, or by a guarded `update-ref` when nothing holds it. Features land on
BRANCH, never on main: a person reviews the branch and merges it with a pull request.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

MAIN = "refs/heads/main"
BRANCH = "refs/heads/lean"   # created at main when missing; main itself never moves


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


def start(repo: str) -> str:
    """The campaign branch's tip, creating the branch at main when it is missing."""
    if subprocess.run(("git", "rev-parse", "--verify", "--quiet", BRANCH), cwd=repo,
                      capture_output=True, check=False).returncode:
        git(repo, "update-ref", BRANCH, git(repo, "rev-parse", "--verify", MAIN), "")
    return git(repo, "rev-parse", "--verify", BRANCH)


def land(repo: str, work: str, base: str, feature: str) -> str:
    """Put commit `work` (made on `base`) on the campaign branch; the new tip.

    If the branch is still at `base` this is a fast-forward. If a person moved it
    meanwhile, the two are merged normally; a conflict refuses, and the branch stays.
    """
    tip = git(repo, "rev-parse", "--verify", BRANCH)
    new = work
    if tip != base:
        merged = subprocess.run(("git", "merge-tree", "--write-tree", tip, work), cwd=repo,
                                capture_output=True, text=True, check=False)
        if merged.returncode:
            raise RuntimeError(f"{feature} and what the branch gained meanwhile change the same lines: "
                               f"{merged.stdout.strip()[-300:] or merged.stderr.strip()[:300]}")
        new = git(repo, "commit-tree", merged.stdout.split("\n", 1)[0].strip(),
                  "-p", tip, "-p", work, "-m", f"Merge {feature} into lean")
    holder = _holding(repo)
    if holder:
        git(holder, "merge", "--ff-only", "--quiet", new)   # moves that checkout's files too
    else:
        git(repo, "update-ref", BRANCH, new, tip)          # only if it is still `tip`
    return new


def _holding(repo: str) -> str:
    """The checkout that has the campaign branch checked out, or ""."""
    path = ""
    for line in git(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            path = line.split(" ", 1)[1]
        elif line == f"branch {BRANCH}":
            return path
    return ""
