"""Disposable Git repositories for supervised self-repair gates."""

import pathlib
import subprocess
import tempfile


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def repository():
    scratch = tempfile.TemporaryDirectory(prefix="campaign-gate-")
    root = pathlib.Path(scratch.name) / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "test@example.test")
    git(root, "config", "user.name", "test")
    (root / "pkg").mkdir()
    (root / "pkg/a.py").write_text("original content\n")
    (root / "pkg/stays.py").write_text("unchanged\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "test: initial fixture")
    return scratch, root
