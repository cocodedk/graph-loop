"""A campaign owns its repository; the launch directory is only an init default."""

from __future__ import annotations

import pathlib
import subprocess


def initial_root() -> pathlib.Path:
    """Only init may take its repository from the environment or cwd."""
    import where
    path = where.repo().resolve()
    return git_root(path) or path


def git_root(path: pathlib.Path) -> pathlib.Path | None:
    """Find the checkout containing a recorded path, including a removed source."""
    while not path.is_dir() and path != path.parent:
        path = path.parent
    done = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True, check=False)
    return pathlib.Path(done.stdout.strip()).resolve() if done.returncode == 0 else None


def project(space) -> str:
    """The name every mail's subject starts with: the recorded repository, else the
    checkout the workspace sits in, else the workspace folder itself."""
    for row in space.events():
        if row.get("kind") in ("init", "repository_declared") and row.get("repo"):
            return pathlib.Path(row["repo"]).name
    return (git_root(space.root.resolve()) or space.root.resolve()).name

