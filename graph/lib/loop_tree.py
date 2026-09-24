"""The worktree this round runs in: the paid one it continues, or a fresh cut.

Split from `loop.py` at the 200-line cap — the order of a task stays there, in
the file whose docstring is that order; `Loop.run_task` asks for its tree in one
line. Nothing here decides anything about the card: it reuses, salvages or cuts,
and says which happened.
"""

from __future__ import annotations

import pathlib

from worktree import Worktree, owned, reuse_or_salvage


def for_this_round(loop, task: dict) -> tuple[Worktree, bool]:
    """This round's tree, and whether it already holds paid work to continue in.

    `task` is this round's own dictionary and is refreshed in place when a lost
    tree makes the card forget what it was pointing at — never replaced, because
    the lane holds the same object.
    """
    task_id = task["id"]
    start = loop.keeper.tip() if loop.keeper else loop.commit
    previous = str(task.get("rebuild_from") or "")
    # A reusable worktree is a real one: non-empty, and carrying git's own
    # worktree marker as a DIRECTORY — Path("").is_dir() is True and names
    # the repository; a `.git` FILE is a linked worktree, which `Worktree.
    # reuse` itself now refuses to adopt, so this pick must agree. Keyed
    # on the tree, not the round: an uncharged outage (B4) can leave round 0 with a real tree to reuse.
    in_place = (not hasattr(owned, "trees") and bool(previous)
                and (pathlib.Path(previous) / ".git").is_dir())
    tree = Worktree(loop.repo, task_id, start)
    stale_why = saved = ""
    if in_place:
        in_place, stale_why, saved = reuse_or_salvage(loop, task_id, tree, previous)
    if in_place:
        loop.space.event("rebuild", task=task_id, path=tree.path,
                         round=int(task.get("rebuild_round") or 0))
        if tree.rebased:
            loop.space.event("tree_rebased", task=task_id,
                             old=tree.rebased[0], new=tree.rebased[1])
    else:
        if previous or task.get("rebuild_round"):   # previous alone: a round-0 outage's tree went stale
            # Nothing to rebuild in place — gone from disk, or its HEAD
            # can no longer be read as the base plus edits — so this
            # round proves red and reviews the contract again, with the
            # findings still in hand. The round COUNT stands: losing a
            # worktree never buys a fourth round.
            loop.space.event("rebuild_lost", task=task_id, lost=previous, why=stale_why, saved=saved)
        tree.create()
        loop.space.event("worktree", task=task_id, path=tree.path, commit=tree.commit)
        if previous or task.get("rebuild_round"):
            # the session belonged to the lost worktree; the card names no tree until a
            # builder is paid. Read FIRST, then written into this round's own dictionary
            fresh = loop.backlog.note(task_id, rebuild_from=None, session="", finished=None)
            task.clear(); task.update(fresh)    # — never over it: the lane holds it too
    claims = loop.space.running()
    if task_id in claims:
        row = claims[task_id]
        loop.space.claim(task_id, again=True, pid=int(row.get("pid") or 0),
                         pgid=int(row.get("pgid") or 0),
                         account=str(row.get("account") or "lane"),
                         worktree=tree.path)
    return tree, in_place
