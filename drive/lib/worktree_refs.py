"""What happens when a builder's own HEAD is not the base plus edits — and,
below, when it is, but the LOOP's own base moved on regardless.

Refs are the driver's — not because a hook polices every write, but because
each task checkout is a private clone with its own `.git`: whatever a
builder does to a ref, however it is spelled, lands only there and is
discarded with the checkout, never reaching the repo. `lib/hooks/reference-
transaction`, installed on every checkout by `Worktree.create`, still
refuses any ref-transaction write it can see from inside it — a commit, a
branch, a switch to a NEW branch, a reset that would move HEAD onto a commit
outside the checkout's own history — but that is a second line of defence
now, not the one thing standing between a builder and the repo.

The driver still reconstructs nothing; it only CHECKS, via `Worktree.on_base`,
that HEAD in the checkout still equals the commit the round started from.
That check stays because isolation cannot help it: a builder holding a shell
can write `.git/HEAD` itself, running no git code and so passing every hook
on every git version — but this only misleads the checkout about its own
history, nothing escapes to the repo, so `on_base` catches it once HEAD is
compared against the base. Split out of `worktree` at the 200-line cap;
`worktree` stays the front door.
"""

from __future__ import annotations

import subprocess

from backlog_status import REBUILD_ROUNDS
from contract import moved_under  # its home; `prompts` only re-exports it
from loop_types import TaskOutcome
from worktree_provision import (
    provision,  # noqa: F401 — `worktree` reaches it through here
)


class HeadMoved(Exception):
    """HEAD in the checkout no longer equals the round's base commit. Most of
    the time that is the builder's own doing, and the hook refused every ref
    write it covers, so the driver cannot know how HEAD got here — only that
    reading this worktree as "the base plus edits" would be wrong. `advance`,
    below, raises it too, for a HEAD the builder never touched: the loop's own
    base moved on and this checkout can no longer be read as that base plus
    edits — a conflicting edit, or no longer even on the same line of
    history. Either way the round fails closed; `why` says which."""

    def __init__(self, found: str, why: str = ""):
        self.found = found
        self.why = why
        super().__init__(found)

    @property
    def said(self) -> str:
        return self.why or f"the builder's HEAD is not the base plus edits ({self.found})"

    @property
    def note(self) -> str:
        return (f"Your previous call left HEAD on {self.found}, off the task's "
                "base. Start the work over from the base in this worktree, "
                "finish, and say DONE.")


def advance(repo: str, path: str, found: str, target: str) -> str | None:
    """Bring a kept checkout up to the loop's current base before it is
    handed back. `found` is the checkout's own HEAD; `target` is where the
    next round should start from. Equal answers None: nothing moved, so
    nothing is done and nothing is said.

    Only a straight-line move is attempted: `found` must be an ancestor of
    `target`. Anything else — a fork, a rewind, a branch rebuilt out from
    under it — is not a checkout worth vouching for as "the base plus
    edits" any more, and raises `HeadMoved` on the spot rather than handing
    back a stale tree unasked. A genuine ancestor moves with a plain
    `checkout --detach`, so git carries the kept, uncommitted edits across
    when they do not conflict — the same as any other checkout. `-c
    core.hooksPath=` is how this one call gets past the very guard
    `Worktree._hooked` put on this checkout for everyone else: the hook
    refuses a builder's `checkout --detach` outright (it moves HEAD by a
    ref write, not a symbolic one), and the driver is not exempt merely by
    asking nicely.

    Either way `HeadMoved` sends the round to a fresh tree instead
    (`lib/loop.py`, the same path a lost worktree already takes); the
    checkout itself is left exactly as it stood.

    Neither raise is for a git failure. `--is-ancestor` exits 1 for a real
    "no" and anything else for an error (`git help git-merge-base`); a stale
    `index.lock` or other checkout failure that is not git's own "would be
    overwritten" refusal is not a conflict either. Both are paid work, so
    both are let through as a plain error instead of a verdict on the tree
    — the turn fails loudly and the tree is left for a person, not discarded
    on a guess.
    """
    if found == target:
        return None
    check = subprocess.run(("git", "-C", repo, "merge-base", "--is-ancestor", found, target),
                           capture_output=True, text=True, check=False)
    if check.returncode == 1:
        raise HeadMoved(found, why="the kept tree's base is not on the branch any more")
    if check.returncode:
        raise RuntimeError(f"git merge-base --is-ancestor {found} {target}: {check.stderr.strip()}")
    moved = subprocess.run(("git", "-C", path, "-c", "core.hooksPath=", "checkout", "-q",
                            "--detach", target), capture_output=True, text=True, check=False)
    if not moved.returncode:
        return target
    if ("would be overwritten by checkout" in moved.stderr
            or "Your local changes" in moved.stderr):
        raise HeadMoved(found, why="the kept edits conflict with what landed on the base since")
    raise RuntimeError(f"git checkout --detach {target}: {moved.stderr.strip()}")


def reuse_or_salvage(loop, task_id: str, tree, previous: str) -> tuple[bool, str, str]:
    """Attach the round to its kept tree; when that tree can no longer be read
    as the base plus edits, its edits are paid work: written down as a diff,
    pointed at from the card, and only then is the tree removed — a death
    between the two would otherwise lose the pointer with the tree. Answers
    (in place, why not, where the edits are)."""
    try:
        tree.reuse(previous)
        return True, "", ""
    except HeadMoved as fault:
        saved = loop.space.artifact(task_id, "lost-edits", tree.diff(binary=True))
        earlier = list(loop.backlog.task(task_id).get("lost_edits") or [])   # a second conflict adds, never replaces
        loop.backlog.note(task_id, lost_edits=earlier + [saved], rebuild_from=None)
        tree.remove()
        return False, fault.said, saved


def save_and_go(loop, task_id: str, tree) -> str:
    """Write down what a tree whose HEAD MOVED holds, point the card at it, and
    only then remove the tree. Answers "" once it is gone, and why not when it
    stays. The one door for both sites that delete such a tree — the builder's
    own move (`discard`, below) and a gate's (`loop_judge_retry`) — because
    each of them used to delete it unread and an hour of paid edits went with
    the directory (astra's round-4 finding 6).

    Against the RECORDED base, not HEAD: HEAD is exactly what cannot be trusted
    here, and edits the builder put inside its own commit leave nothing in a
    diff against it.

    A save that FAILS keeps the tree — it is the only copy of that work, and
    what authorises a deletion is the save succeeding, never the fault that
    ordered it. The card says which tree (`edits_unsaved`, which `sweep_trees`
    honours); no keep-note is written beside it, because whatever stopped the
    diff — a full disk is how this campaign met it — stops that too.

    A card sliced away while the round ran is no longer there to point; the
    diff is on the platter under `calls/<task>/` either way.
    """
    try:
        saved = loop.space.artifact(task_id, "lost-edits",
                                    tree.diff(binary=True, against=tree.commit))
    except (OSError, RuntimeError) as fault:
        why = f"the paid edits in {tree.path} could not be saved: {fault!r}"[:300]
        loop.space.alert(task_id, why)
        if loop.backlog.task(task_id) is not None:
            loop.backlog.note(task_id, edits_unsaved=why)
        return why
    current = loop.backlog.task(task_id)
    if current is not None:   # a second loss adds to the list, never replaces it
        loop.backlog.note(task_id, lost_edits=list(current.get("lost_edits") or []) + [saved])
    tree.remove()
    return ""


def discard(loop, task: dict, tree, fault: HeadMoved) -> TaskOutcome:
    """Resolve a HeadMoved fault. Unlike every other harness fault, this tree
    is never REUSED — it cannot be read as edits on the base. The round is
    charged the same as any harness fault, but `rebuild_from` stays unset, so
    the next round cuts a fresh tree from the campaign base, never this
    foreign tip. What the tree HOLDS is still paid work: saved and pointed at
    from the card before it goes, and the tree kept where it is when that save
    fails (`save_and_go`).
    """
    task_id = task["id"]
    unsaved = save_and_go(loop, task_id, tree)
    why = (f"{fault.said}; its HEAD left the base, so the worktree was "
           + (f"kept where it is — {unsaved}" if unsaved else "saved and discarded"))
    with loop.backlog.only_writer():     # guard and write in one hold
        # The builder call took an hour, and a drop, a hold or a rewrite decided
        # in it is newer than this fault: `todo` over a drop puts the card back
        # in the queue to be built again (astra round 4, finding 2). The salvage
        # above is not that kind of write — it is the loop's own pointer at paid
        # work, and skipping it would lose what this guard exists to protect.
        moved = moved_under(loop.backlog.task(task_id), task)
        if moved:
            loop.space.event("card_moved", task=task_id, step="discard", why=moved)
            return TaskOutcome("held", moved, tree.path)
        rounds = int(task.get("rebuild_round") or 0) + 1
        if rounds < REBUILD_ROUNDS:
            loop.space.event("rebuild_queued", task=task_id, round=rounds, why=why)
            loop.backlog.set_status(task_id, "todo", rebuild_round=rounds, rebuild_from=None,
                                    rejections=list(task.get("rejections") or []) + [fault.note],
                                    refused_why=None)
            return TaskOutcome("harness", why, tree.path)
        loop.space.event("rejected", task=task_id, why=why)
        loop.backlog.set_status(task_id, "rejected", rebuild_round=rounds, rebuild_from=None,
                                refused_why=why)
        return TaskOutcome("rejected", why, tree.path)
