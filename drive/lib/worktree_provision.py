"""The generated, gitignored material a checkout needs but git never carries.

Without a repository's minted secrets, every test that opens a door dies at the
token exchange and a gate reports a redness the repository does not have. What
that material is belongs to the repository being worked on, so two environment
variables name it, as comma-separated paths relative to the repository root:

    DRIVE_PROVISION_LINK=simulation/.venv          symlinked, never copied
    DRIVE_PROVISION_COPY=simulation/secrets,simulation/.env

A repository that names neither gets a plain checkout, which is what most want.

Provisioning has no tie to refs; it sat in `worktree_refs` only for room under
`worktree.py`'s 200-line cap, and moved here when that file reached the same
cap. `worktree_refs` imports it back, so `worktree` stays the front door.
"""

from __future__ import annotations

import os
import pathlib
import shutil


def _named(variable: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in os.environ.get(variable, "").split(",")
                 if part.strip())


def provision(path: str, repo: str) -> None:
    for name in _named("DRIVE_PROVISION_LINK"):
        source, target = pathlib.Path(repo) / name, pathlib.Path(path) / name
        if source.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source)
    for name in _named("DRIVE_PROVISION_COPY"):
        source, target = pathlib.Path(repo) / name, pathlib.Path(path) / name
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)   # a checkout may not carry the folder
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        elif source.is_file():
            shutil.copy2(source, target)
