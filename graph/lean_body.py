"""What a lean loop says: to its builder, and in a new pull request."""

from __future__ import annotations

import pathlib


def pr_body(spec_path: str, why: str, found: str) -> str:
    """What a new pull request says: the suite, the reviewer's verdict and its findings."""
    said = "accepted it" if not why else "still did not accept it after the last repair"
    return (f"Built by graph-loop's lean loop from `{pathlib.Path(spec_path).name}`: the suite "
            f"is green, and an independent reviewer {said}."
            + (f"\n\nThe reviewer's findings:\n\n{found}" if found else ""))


def builder_prompt(spec: str, script: str, profile_path: str, lessons: str, own_gate: bool) -> str:
    """What the builder is told. A card with its own fast gate runs only that: the loop runs the full
    suite after the build and hands back any failure. Any builder is barred from background jobs,
    because each wait is a paid turn (one card spent about $75 polling a 25-minute suite)."""
    run = (f"Run this card's own gate with `bash {script}` and leave it green, never the full suite: "
           f"the loop runs that after you finish and hands you any failure" if own_gate
           else f"Run the suite with `bash {script}` and leave it green")
    return (f"Implement what this spec asks, including its tests. Follow the repository's "
            f"CLAUDE.md and the profile at {profile_path}. {run}. And never start or wait on a "
            f"background job: every wait is a paid turn. Do not commit: the loop commits.\n\n"
            f"## Spec\n\n{spec}{lessons}")
