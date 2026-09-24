"""A gate's wall time, against the same gate run alone.

Split from `throttle.py` at the 200-line cap. It is the one signal that has to
read the campaign's own history rather than the machine, and it is a NICETY:
the throttler works without it, so a log it cannot read costs this turn's ratio
and nothing else (`throttle.Throttle._close` keeps the machine's reading first,
where a failure here cannot reach it).
"""

from __future__ import annotations


def ratio(space, state: dict, turn_id: str, ran: int) -> float | None:
    """The worst gate of this turn against the same card's gate run alone.

    A gate is the one step whose wall time means something across turns, and
    only against ITSELF: two cards' gates are two different programs. A turn
    that ran one lane is what teaches a card's lone time.

    Only gates that PASSED are timed. Red-first and a first round leave
    tenth-of-a-second failures in the record, and one of those taken as a lone
    time made the same gate passing in ten seconds read as a hundredfold
    slowdown (`loop_judge.judge` records `passed` on every gate it runs).

    Every duration it reads is the loop's one clock — `workspace.step` times a
    step with `time.monotonic`, so a wall clock stepping backwards cannot teach
    a gate a lone time shorter than it really took.

    `state["gate_alone"]` is grown here and kept by the caller.
    """
    alone = dict(state.get("gate_alone") or {})
    worst = None
    for row in space.events():
        if row.get("kind") != "step" or row.get("step") != "gate":
            continue
        if turn_id and row.get("turn") != turn_id:
            continue
        if row.get("passed") is not True:
            continue
        task, seconds = str(row.get("task") or ""), float(row.get("seconds") or 0)
        if seconds <= 0:
            continue
        if ran <= 1:
            alone[task] = seconds
        elif alone.get(task):
            worst = max(worst or 0.0, seconds / alone[task])
    state["gate_alone"] = alone
    return worst
