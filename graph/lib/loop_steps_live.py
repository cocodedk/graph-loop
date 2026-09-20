"""How a live builder's call that did not answer ends. Split from
`loop_steps` at the 200-line cap; `build` there calls in."""

from __future__ import annotations

from loop_peers import lost_why, open_why, restate_live_peers
from loop_types import TaskOutcome


def live_call_lost(loop, task_id: str, tree, built, in_place: bool) -> TaskOutcome:
    """A live builder that did not answer may have acted before it stopped:
    a limit or a crash is no proof the stack is untouched, and a retry would
    repeat a live action. A person looks at the stack first. A refused
    session is not that: the call never reached the model, so no helper verb
    ran and the stack is untouched. Saying otherwise sent me to inspect a
    stack that had not moved since the day before."""
    if built.unstarted:
        why = ("every account refused this call before its first turn — an expired session or a "
               "usage limit — so it never reached the model and the stack is untouched; clear "
               "whichever refused and unhold this card")
        # todo AND blocked_by_human: `startable` skips a held card, so it is not
        # picked again while no account can sign in, and `waiting_for_human` reads
        # `ready`, which counts only todo — a "held" status would vanish from the
        # board's own list of what waits for a person.
        loop.backlog.set_status(task_id, "todo", blocked_by_human=True,
                                held_by="loop", refused_why=why)
        loop.space.event("needs_a_person", task=task_id, why=why)
        loop.space.alert(task_id, why)
        # A reused tree holds the rounds before it: only a tree this call made is empty
        # — that one is removed and forgotten.
        if in_place:
            return TaskOutcome("blocked", why, tree.path)
        tree.remove()      # no model ran, so the tree holds nothing to salvage
        loop.backlog.note(task_id, rebuild_from=None)
        return TaskOutcome("blocked", why, "")
    why = f"the live builder's call did not return ({built.kind}); the stack may hold a half-done action — inspect it before re-queuing"
    loop.backlog.set_status(task_id, "live_call_lost", refused_why=why)
    # They are already held with OPEN_WHY, and this turn's release would free
    # them. The doubt is what outlives the turn, so it is what they now say.
    restate_live_peers(loop.backlog, open_why(task_id), lost_why(task_id))
    loop.space.event("needs_a_person", task=task_id, why=why)
    loop.space.alert(task_id, why)
    tree.keep("a live call that did not return")
    return TaskOutcome("blocked", why, tree.path)
