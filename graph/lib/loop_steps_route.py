"""Which resource and effort build this task, from the card router.

Split out of loop_steps.py at the 200-line cap. See docs/ROUTER.md.
"""

from __future__ import annotations

import model_router
import resources


def routed_build(loop, task: dict) -> tuple[str, list]:
    """The router's pick, first in the belt to try; the rest of the
    configured builders follow in their own order, so a refusal before
    reading still walks every resource, at the one effort the route chose."""
    choice = model_router.choose(task, "build", space=loop.space)
    ordered = [choice.resource] + [one for one in resources.belt("build")
                                   if one != choice.resource]
    return choice.effort, ordered


def note_builder(loop, task_id: str, resource) -> None:
    """The resource that actually built this round, for the review after it
    to infer the builder's family from (`docs/ROUTER.md`) — never guessed
    from a model name, since a configured alias is still the same agent."""
    loop.backlog.note(task_id, builder_model=resource.model, builder_agent=resource.agent)
