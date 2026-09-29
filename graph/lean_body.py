"""What a lean loop's new pull request says."""

from __future__ import annotations

import pathlib


def pr_body(spec_path: str, why: str, found: str) -> str:
    """What a new pull request says: the suite, the reviewer's verdict and its findings."""
    said = "accepted it" if not why else "still did not accept it after the last repair"
    return (f"Built by graph-loop's lean loop from `{pathlib.Path(spec_path).name}`: the suite "
            f"is green, and an independent reviewer {said}."
            + (f"\n\nThe reviewer's findings:\n\n{found}" if found else ""))
