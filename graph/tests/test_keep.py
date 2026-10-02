"""A throwaway git repository with one commit, for tests that need a real checkout."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit


def repo() -> str:
    root = tempfile.mkdtemp()
    for args in (("git", "init", "-q", "-b", "main"),
                 ("git", "config", "user.email", "t@example.test"),
                 ("git", "config", "user.name", "test")):
        subprocess.run(args, cwd=root, capture_output=True, check=True)
    (pathlib.Path(root) / "a.py").write_text("one\n")
    subprocess.run(("git", "add", "-A"), cwd=root, capture_output=True, check=True)
    subprocess.run(("git", "commit", "-qm", "first"), cwd=root, capture_output=True,
                   check=True)
    return root


def sha(root: str, ref: str = "HEAD") -> str:
    return subprocess.run(("git", "-C", root, "rev-parse", ref), capture_output=True,
                          text=True, check=True).stdout.strip()
