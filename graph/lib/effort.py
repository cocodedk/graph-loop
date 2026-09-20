"""How hard to think about a task — decided per call, from the task itself.

No pre-flight model call: a card already says how big it is, and a round that
failed says the last setting was not enough. Two signals, both free:

  weight   the contract's own shape — how many files it touches, whether its
           gate acts on the live stack, how much the done-when demands, and
           whether the commander marked it hard.
  rounds   what already failed: a rebuild round, a replan, a rejected review.

The ladder rises with the sum and never falls inside a task. Every choice is
recorded with the call, so the ladder can be corrected from evidence rather
than from taste (a lesson: effort is not the lever when a gate fails — but
a rejected review IS evidence that this task deserves more thought).
"""

from __future__ import annotations

from backlog_status import is_live

# No `max` on either ladder: it cost twelve minutes a review and found what
# high finds (the owner, 2026-08-30). xhigh is the builder's ceiling, high the reviewer's.
BUILD_LADDER = ("medium", "high", "xhigh")
REVIEW_LADDER = ("low", "medium", "high")


def weight(task: dict) -> int:
    """0 for a one-file card, up to 3 for a live or commander-marked one."""
    score = 0
    if is_live(task):
        score += 2                      # a live card acts on the stack: think first
    if task.get("hard_review"):
        score += 2                      # the commander said so
    if len(task.get("files") or []) >= 4:
        score += 1
    if len(str(task.get("done_when") or "")) > 1200:
        score += 1                      # a long contract carries many rules
    return score


def rounds_lost(task: dict) -> int:
    return int(task.get("rebuild_round") or 0) + int(task.get("replans") or 0)


def _rung(ladder: tuple, task: dict, floor: int) -> str:
    """The floor, plus what the card weighs, plus what has already failed."""
    return ladder[min(len(ladder) - 1, floor + weight(task) + rounds_lost(task))]


def build_effort(task: dict) -> str:
    """A builder starts at high for a small card and climbs with the task."""
    return _rung(BUILD_LADDER, task, floor=1)      # never below high: builders write code


def review_effort(task: dict) -> str:
    """A reviewer starts medium on a small card and reaches high for a live one
    or a round that already failed."""
    return _rung(REVIEW_LADDER, task, floor=1)     # never below medium
