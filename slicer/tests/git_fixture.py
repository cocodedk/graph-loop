"""Commit fixture files so validation reads the same Git snapshot as production."""

import subprocess


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def commit(repo):
    if not (repo / ".git").exists():
        git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.test",
        "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
    return git(repo, "rev-parse", "HEAD")
