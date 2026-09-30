"""What a lean change carries that nobody asked for: new files with leftover names."""

from __future__ import annotations

import re

# An editor's or a patch's or a cache's leavings: a builder that leaves one passes the suite and the review.
LEFTOVER = re.compile(r"(\.(orig|rej|bak|swp|swo|tmp|pyc|pyo)$|~$|(^|/)\.DS_Store$"
                      r"|(^|/)(__pycache__|node_modules|\.pytest_cache|\.ruff_cache|\.mypy_cache)/)")


def _path(header: str) -> str | None:
    """The new path in a `diff --git` line of an added file, whose two paths are the same. Git quotes a path
    with unusual bytes (`"a/caf\\303\\251" "b/caf\\303\\251"`); an escape is read as one character, which keeps the
    name's ending, and an unquoted path may itself hold ` b/`, so it is cut in the middle."""
    rest = header[len("diff --git "):]
    if rest.startswith('"'):
        quoted = re.fullmatch(r'"a/(.*)" "b/(.*)"', rest)
        return re.sub(r"\\(?:[0-7]{3}|.)", "?", quoted.group(2)) if quoted else None
    size = (len(rest) - 5) // 2
    return rest[2:2 + size] if len(rest) % 2 == 1 and size > 0 else None


def new_files(diff: str) -> list[str]:
    """The paths a diff adds, in order (`new file mode` follows its `diff --git` line)."""
    lines, added = diff.splitlines(), []
    for index, line in enumerate(lines):
        adds = line.startswith("diff --git ") and index + 1 < len(lines) and lines[index + 1].startswith("new file")
        if adds and (path := _path(line)):
            added.append(path)
    return added


def leftovers(diff: str) -> list[str]:
    """The new files whose names say they were left behind."""
    return [path for path in new_files(diff) if LEFTOVER.search(path)]
