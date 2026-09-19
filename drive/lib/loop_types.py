"""The two names every step shares."""

from __future__ import annotations

import dataclasses

import accounts

# Every account, in order, without preference: a build walks them until one answers,
# so a limit or an expired session on the first spends the second rather than sparing
# it. The owner, 2026-08-31: use all resources without discrimination. The table itself is
# lib/accounts.py, and adding one is a line of data there or DRIVE_ACCOUNTS.
ACCOUNTS = accounts.names()


@dataclasses.dataclass
class TaskOutcome:
    state: str          # done | failed | rejected | refused | waiting | held | harness
    why: str = ""
    worktree: str = ""
