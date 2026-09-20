"""What a round already finished, so the next one does not pay for it twice.

A reviewer outage after a green gate used to send work that already stands
through another builder call (Astra's finding 22). The card remembers the phase
that finished, the tree it finished in, the contract it was built under and the
diff as it stood; a retry that matches all four re-runs only what is missing,
and any difference — a rebased tree, an edited contract, a changed diff — falls
back to the ordinary path.

Written by the site that KNOWS the phase finished (`loop_judge`, after its own
green gate), never inferred from which kind of caller a retry came from.
"""

from __future__ import annotations

import hashlib

from prompts import contract_digest


def finished(task: dict, tree, phase: str, diff: str) -> dict:
    """The record of a finished phase, as the card holds it.

    The base is in it because the diff cannot stand in for it: a tree advanced
    onto commits that touched OTHER files comes back with the same diff, word
    for word, and the phase was finished beside work that was not there yet.
    """
    return {"phase": phase, "tree": tree.path, "base": tree.commit,
            "contract": contract_digest(task),
            "diff": hashlib.sha256(diff.encode("utf-8")).hexdigest()[:16]}


def resuming(loop, task: dict, tree, phase: str) -> bool:
    """Whether `phase` finished in THIS tree, on the base this round starts
    from, under the contract it reads, with the tree as it was left.

    Read once: the record is dropped whether it matched or not, so a round that
    is sent back with findings can never skip the builder on the strength of an
    older tick.
    """
    record = task.get("finished") or {}
    if not record:
        return False
    loop.backlog.note(task["id"], finished=None)
    return record == finished(task, tree, phase, tree.diff())
