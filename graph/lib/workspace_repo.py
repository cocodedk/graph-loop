"""A campaign owns its repository; the launch directory is only an init default."""

from __future__ import annotations

import os
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


def repository(space, *, persist: bool = True) -> pathlib.Path:
    rows = space.events()
    for row in rows:
        if row.get("kind") in ("init", "repository_declared") and row.get("repo"):
            return pathlib.Path(row["repo"])
    root = _derive(space, rows)
    if persist:
        space.event("repository_declared", repo=str(root))
    return root


def _derive(space, rows: list[dict]) -> pathlib.Path:
    from finishing import declared_sources
    sources = [pathlib.Path(name) for name in declared_sources(space)]
    roots = {root for path in sources if path.is_absolute()
             if (root := git_root(path)) is not None}
    if len(roots) > 1:
        raise SystemExit("approved sources name different repositories")
    if roots:
        return roots.pop()
    # Sources were stored repo-relative. Their anchors are campaign facts,
    # never the process's cwd: the absolute backlog first, then the workspace.
    backlog = next((row.get("backlog", "") for row in rows
                    if row.get("kind") == "init"), "")
    anchors = [pathlib.Path(backlog), space.root.resolve()]
    for anchor in anchors:
        if anchor.is_absolute() and (root := git_root(anchor)) is not None \
                and all((root / source).exists() for source in sources):
            return root
    # An explicit setting can locate an old campaign stored entirely outside
    # its repository. Persist it too; later calls cannot silently redirect it.
    if configured := os.environ.get("GRAPH_REPO"):
        path = pathlib.Path(configured).resolve()
        return git_root(path) or path
    raise SystemExit("cannot derive this workspace's repository from its approved sources; "
                     "set GRAPH_REPO once to record it")


def alert_cwd(space, root: pathlib.Path) -> None:
    """Name a different launch repository once per campaign, never per card."""
    cwd_root = git_root(pathlib.Path.cwd())
    if cwd_root is None or cwd_root == root:
        return
    # Linked worktrees are different checkouts of the same repository.
    def common(path):
        done = subprocess.run(["git", "-C", str(path), "rev-parse",
                               "--path-format=absolute", "--git-common-dir"],
                              capture_output=True, text=True, check=False)
        return done.stdout.strip() if done.returncode == 0 else None
    if common(cwd_root) == common(root):
        return
    subject = "workspace repository"
    if not any(row.get("kind") == "alert" and row.get("task") == subject
               for row in space.events()):
        space.alert(subject, f"using recorded repository {root}; "
                    f"the working directory belongs to {cwd_root}")
