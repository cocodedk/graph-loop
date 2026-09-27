"""The generated, gitignored material a checkout needs but git never carries.

Without a repository's minted secrets, every test that opens a door dies at the
token exchange and a gate reports a redness the repository does not have. What
that material is belongs to the repository being worked on, so two environment
variables name it, as comma-separated paths relative to the repository root:

    GRAPH_PROVISION_LINK=simulation/.venv          symlinked, never copied
    GRAPH_PROVISION_COPY=simulation/secrets,simulation/.env

A repository that names neither gets a plain checkout, which is what most want.

Provisioning has no tie to refs; it sat in `worktree_refs` only for room under
`worktree.py`'s 200-line cap, and moved here when that file reached the same
cap. `worktree_refs` imports it back, so `worktree` stays the front door.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess


def named(variable: str) -> tuple[str, ...]:
    """The paths a variable names, spelled one way: `node_modules/` is `node_modules`.
    `normpath` never follows a link, so a linked folder keeps its own name."""
    return tuple(os.path.normpath(part.strip()) for part in os.environ.get(variable, "").split(",")
                 if part.strip())


def carried(path: str) -> list[str]:
    """What git would carry into this checkout's diff from what `provision` put there.

    Provisioned material must be ignored. A linked folder is a symlink, which git
    treats as a file, so a pattern for folders such as `node_modules/` does not
    ignore it: in one campaign the link entered every build's diff and 352 attempts
    kept nothing. Asking `git status` rather than one path's ignore rule also passes
    a copied folder whose contents are ignored one by one.
    """
    present = [name for name in named("GRAPH_PROVISION_LINK") + named("GRAPH_PROVISION_COPY")
               if os.path.lexists(os.path.join(path, name))]
    if not present:
        return []
    # a name is a path, never pathspec magic (`:cache` would read as `cache`); the flag,
    # unlike a `:(literal)` prefix, means the same whatever GIT_*_PATHSPECS says
    shown = subprocess.run(["git", "--literal-pathspecs", "-C", path, "status", "--porcelain",
                            "--untracked-files=all", "--", *present],
                           capture_output=True, text=True, check=True)
    return [line for line in shown.stdout.splitlines() if line.strip()]


def provision(path: str, repo: str) -> None:
    for name in named("GRAPH_PROVISION_LINK"):
        source, target = pathlib.Path(repo) / name, pathlib.Path(path) / name
        if source.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source)
    for name in named("GRAPH_PROVISION_COPY"):
        source, target = pathlib.Path(repo) / name, pathlib.Path(path) / name
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)   # a checkout may not carry the folder
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        elif source.is_file():
            shutil.copy2(source, target)
