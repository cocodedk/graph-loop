"""What a campaign is pointed at, read from its own init event: its backlog
and its branch.

One home for each answer: `graph_commands._backlog_of` turns an empty backlog
into an exit (every command here needs a real path or a reason to stop), and
`view_sections._current_backlog` turns it into the environment's default (a
dashboard on a campaign nobody has started yet still has something to show).
"""

from __future__ import annotations

import pathlib

import where
from view_base import recorded_branch


def branch_of(space) -> str:
    """The branch this campaign keeps its work on: the one its init event
    recorded, the environment's otherwise (`where.branch()`).

    THE reading — the driver builds its keeper with it and handoff-standin.sh
    briefs the stand-in with it, so a stand-in can never be pointed at a
    branch its own driver is not using. Two readings of this meant one
    campaign was told it had no branch while its keeper pushed to one
    (astra round 4, finding 14)."""
    return recorded_branch(space.events(), where.branch())


def backlog_of(space) -> str:
    """The backlog path named in the campaign's own init event. A relative
    path is read against the repository when it lives there (this campaign's
    does, and `status` from another directory used to fail on it); otherwise
    it is returned as recorded, so an init made elsewhere keeps its meaning.
    `""` when there is no init event yet — a fresh, unstarted campaign.

    That empty answer is a real path to nowhere, and it must never reach
    `pathlib.Path`, which reads it as the current directory. `Backlog` refuses
    it at its constructor for exactly that reason: a campaign whose `approve`
    ran before its `init` recorded no init event, so this answered `""`, and a
    whole plan phase wrote seven molecules, its trace and its lock into the
    driver's own directory — reporting every one of them as published
    (2026-09-18). `graph_commands._backlog_of` exits on it for its own
    commands; the plan phase reached this function around that."""
    for row in space.events():
        if row.get("kind") == "init":
            path = pathlib.Path(row["backlog"])
            in_repo = where.repo() / path
            return str(in_repo if not path.is_absolute() and in_repo.exists() else path)
    return ""
