"""Review the finished diff; a malformed answer retries only the missing review."""
from __future__ import annotations

import json

import review_scope
from backlog_status import is_live
from effort import review_effort
from loop_judge_retry import _send_back, back_in_place
from loop_resume import finished
from prompts import DiffTooLarge, diff_prompt
from providers import Outcome


def review_change(loop, task: dict, tree, rebuild: int):
    task_id = task["id"]
    diff = tree.diff()
    loop.space.artifact(task_id, "diff", diff)
    try:
        prompt = diff_prompt(task, diff)
    except DiffTooLarge as oversized:
        # Too large for the reviewer to read whole, so it is not read at all.
        # Otherwise this ends the round exactly the way a REJECT verdict does:
        # back to the builder with the finding, to the round cap, so it can
        # reduce the change or split the card.
        why = (f"the diff is {oversized.size} characters, over the {oversized.limit} "
               "the reviewer can read whole — reduce it or split the card")
        return _send_back(loop, task, tree, rebuild, why)
    with loop.space.step(task_id, "diff_review") as note:
        verdict = loop.review(prompt, effort=review_effort(task), cwd=tree.path,
                              space=loop.space, task_id=task_id)
        note(verdict=verdict.verdict, outcome=verdict.kind)
    loop.space.artifact(task_id, "diff-review-answer", verdict.raw or verdict.text)
    if verdict.ok:
        try:
            body = review_scope.validate(verdict.text, diff)
        except ValueError as error:
            verdict = Outcome("malformed", text=str(error), raw=verdict.raw)
        else:
            loop.space.artifact(task_id, "diff-review-observations",
                                json.dumps(body["observations"], ensure_ascii=False))
            verdict = Outcome("ok", verdict=body["review"], text=review_scope.summary(body))
    if not verdict.ok:
        # The reviewer was limited, killed or answered nothing — the harness
        # talking, not a finding. The gate already passed in this tree, so the
        # card goes back as a counted round HERE: a card left plain todo was
        # re-picked into a fresh tree that re-paid the whole build, for ever.
        loop.space.event("review_unavailable", task=task_id, step="diff_review",
                         why=f"{verdict.kind}: {verdict.text[:200]}")
        return back_in_place(loop, task, tree, "harness",
                             f"the diff review did not happen ({verdict.kind})",
                             "The previous round's diff review did not happen — a harness "
                             "fault, not a finding. The work in this worktree already passed "
                             "its gate: confirm it stands and say DONE.",
                             review_kind=verdict.kind,
                             # the gate finished HERE, on this diff: the next
                             # attempt reviews it again and calls no builder.
                             # Never a live card: its round is held for a person
                             # either way, and a resumed one would run the live
                             # gate without the `live_call_open` build() writes.
                             finished=(None if is_live(task) else
                                       finished(task, tree, "gate", diff)))
    if verdict.verdict != "ACCEPT":
        return _send_back(loop, task, tree, rebuild, verdict.text)

    return None
