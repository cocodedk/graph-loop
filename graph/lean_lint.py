"""The profile's optional lint command: run before the suite, in the same gate box."""

from __future__ import annotations

from collections.abc import Callable
from typing import Self


class Commands(str):
    """The suite's command, carrying the lint command with it so `lean_run.check` keeps its signature."""

    lint: str

    def __new__(cls, suite: str, lint: str = "") -> Self:
        command = super().__new__(cls, suite)
        command.lint = lint
        return command


def run(ws, masked: Callable, suite: str, cwd: str, feature: str, round_: int) -> str:
    """Why the lint is red ("" when it is green or the profile has none), as a red suite's reason reads."""
    command = getattr(suite, "lint", "")
    if not command:
        return ""
    passed, tail = masked(ws, command, cwd)
    ws.event("lean_lint", task=feature, round=round_, passed=passed, tail=tail[-2000:])
    # `tail` is the gate's own excerpt (`gate_reports.excerpt`): cut again, it can lose the failing line
    return "" if passed else f"Fix the red lint. Run {command}, then fix the findings shown below:\n{tail}"
