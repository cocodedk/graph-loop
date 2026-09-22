"""Which resource and effort build this task, from the card router.

Split out of loop_steps.py at the 200-line cap. See docs/ROUTER.md.
"""

from __future__ import annotations

import model_router


def routed_build(loop, task: dict) -> tuple[str, list]:
    """The router's pick, first in the belt to try; the rest of the
    configured builders follow in their own order, so a refusal before
    reading still walks every resource, at the one effort the route chose."""
    choice = model_router.choose(task, "build", space=loop.space)
    ordered = [choice.resource] + [one for one in model_router.candidates("build", task=task)
                                   if one != choice.resource]
    return choice.effort, ordered


def note_builder(loop, task_id: str, resource) -> None:
    """Record the actual builder so review excludes its model on every rung."""
    loop.backlog.note(task_id, builder_model=resource.model, builder_agent=resource.agent)
