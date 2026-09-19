"""Where an answer's paths may point: the anchors it cites and the repository
they must stay inside.

Split from `contracts` at the 200-line cap; `contracts` stays the front door
and re-exports all three names. This half asks about the FILE SYSTEM — does this
line exist, is this path inside the approved sources — while what is left
there asks about the answer's shape.
"""

from __future__ import annotations

import pathlib


def _strings(value: object, what: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{what} must be a list of strings")
    return value


def _sources(anchors: object, repo: pathlib.Path, approved: list[pathlib.Path]) -> None:
    values = _strings(anchors, "source")
    if not values:
        raise ValueError("source must hold at least one exact anchor")
    for anchor in values:
        raw, mark, number = anchor.rpartition(":")
        if not mark or not number.isdigit():
            # Say what is wrong with THIS value, not what the rule is. "source
            # anchor must be repo/path:line: <path>:13-17" quotes a value that
            # appears to satisfy the pattern it is being refused against, and a
            # planner handed it back re-planned the goal three rounds running
            # and never touched the anchor (2026-09-18).
            why = (f"a range, and an anchor cites ONE line: write {raw}:{number.split('-')[0]}"
                   if mark and "-" in number else
                   "no line number: write repo/path:line, such as docs/spec.md:13")
            raise ValueError(f"source anchor {anchor!r} is {why}")
        path = _inside(repo, raw, "source")
        if not any(path == root or path.is_relative_to(root) for root in approved):
            raise ValueError(f"source is outside the approved paths: {raw}")
        if not path.is_file() or int(number) not in range(1, len(path.read_text("utf-8").splitlines()) + 1):
            raise ValueError(f"source anchor does not exist: {anchor}")


def _inside(root: pathlib.Path, raw: str, what: str) -> pathlib.Path:
    if not isinstance(raw, str) or pathlib.Path(raw).is_absolute():
        raise ValueError(f"{what} path must be repository-relative")
    path = (root.resolve() / raw).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"{what} path escapes the repository: {raw}")
    return path
