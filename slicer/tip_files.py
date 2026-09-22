"""The files a plan may depend on belong to a Git tip, never the checkout."""

from __future__ import annotations

import pathlib
import subprocess

from keep_branch import resolve


def reader(repo: pathlib.Path, tip: str):
    """Read each path once from the campaign snapshot. Missing paths return None."""
    if tip.startswith("refs/heads/"):
        tip = resolve(str(repo), tip)  # a branch lookup must never fall back to a tag
    seen: dict[str, str | None] = {}

    def read(path: str) -> str | None:
        relative = pathlib.PurePosixPath(path)
        if not tip or relative.is_absolute() or ".." in relative.parts:
            return None
        if path not in seen:
            result = subprocess.run(["git", "-C", str(repo), "show", f"{tip}:{relative}"],
                                    capture_output=True, check=False)
            seen[path] = result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None
        return seen[path]

    return read
