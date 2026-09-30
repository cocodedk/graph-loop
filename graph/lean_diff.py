"""What a lean change carries that nobody asked for: new files with leftover names."""

from __future__ import annotations

import re

# An editor's or a patch's or a cache's leavings: a builder that leaves one passes the suite and the review.
LEFTOVER = re.compile(r"(\.(orig|rej|bak|swp|swo|tmp|pyc|pyo)$|~$|(^|/)\.DS_Store$"
                      r"|(^|/)(__pycache__|node_modules|\.pytest_cache|\.ruff_cache|\.mypy_cache)/)")


def new_files(diff: str) -> list[str]:
    """The paths a diff adds, in order (`new file mode` follows its `diff --git` line)."""
    lines, added = diff.splitlines(), []
    for index, line in enumerate(lines):
        if line.startswith("diff --git a/") and index + 1 < len(lines) and lines[index + 1].startswith("new file mode"):
            added.append(line[len("diff --git a/"):].split(" b/", 1)[0])
    return added


def leftovers(diff: str) -> list[str]:
    """The new files whose names say they were left behind."""
    return [path for path in new_files(diff) if LEFTOVER.search(path)]
