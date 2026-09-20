"""Spin detection: the same task ending the same way twice.

Split out of `watchdog.py` to hold that file under the 200-line cap.
`watchdog.check` is still the loop's one door for a spin verdict.
`ending_signature` is also imported directly, by `workspace.needs_slice`, to
group a task's gate failures the same way this file groups a spin, and so is
`spends_failures`, the boundary that says which of them are already answered.
Both readers call both, so they never disagree about what is the same ending
or about which endings a recovery has already answered.
"""

from __future__ import annotations

import collections

from view_stamps import TICKING  # the board's counter blanker; one rule, not a copy

REPEAT_LIMIT = 2          # the same ending twice is a spin
ENDINGS = ("refused", "rejected", "failed")
SPIN_RESET = ("quarantined", "spin_spent")  # the last decision about a spin, written or truthfully skipped


def spends_failures(row: dict) -> bool:
    """Whether this row answers its own task's endings before it, the boundary
    both `spinning` and `workspace.needs_slice` count from: a quarantine, a
    spent spin, a replan, a slice that actually planned, or an applied decision.
    `slice_finished` is written for
    every answered slicer call, a refusal and an outage included; those carry a
    non-zero rc and rewrote nothing, so they answer nothing either.

    `decided` is written only where a decision was APPLIED to a card that runs
    on — a rewrite or a requeue; a drop writes `dropped`, and
    a dropped card is settled. So the card is answered here for the endings
    before it, exactly as a replan answers them. It spends none of the
    planner's own budget: that is counted on disk, per request, and a recovery
    boundary is not a new allowance.
    """
    kind = row.get("kind")
    return kind in SPIN_RESET + ("replanned", "slice_finished", "decided") \
        and (kind != "slice_finished" or row.get("rc") == 0)


def ending_signature(row: dict) -> tuple:
    """What makes two endings 'the same': the task, the step and the WHOLE
    reason, with its ticking counters blanked and its spacing collapsed.

    A 120-character prefix used to stand in for the reason, and it lied both
    ways: gate output is kept as its last 400 characters (`loop_judge.py`), so
    whole families of different failures share a prefix and were parked as one
    spin, while a unittest tail's own elapsed time ("Ran 1028 tests in
    12.345s") made the same failure read differently every run, so the spin the
    watchdog exists to catch was never seen.
    """
    # ponytail: TICKING blanks any number before s/m/h/GB, so two failures
    # differing only in such a number read as one. Narrow it if that shows.
    why = " ".join(TICKING.sub("#", str(row.get("why") or "")).split())
    return (row.get("task"), row.get("step") or row.get("kind"), why)


def spinning(since_accept: list[dict]) -> tuple[str, str] | None:
    """The (task, why) of the first ending repeated REPEAT_LIMIT times, or None.

    A boundary (`spends_failures`: a quarantine, a spent spin, a replan or a
    slice that planned) spends the endings of ITS OWN task only: last_boundary holds each
    task's latest boundary index, found by scanning the whole record first —
    a boundary always comes after the endings it spends, so building the dict
    in its own pass (rather than mid-scan) is what lets it spend endings that
    come before it in the record. A global cut once let T1's boundary erase a
    T2 ending recorded before it too.
    """
    last_boundary: dict[str, int] = {}
    for index, row in enumerate(since_accept):
        if spends_failures(row):
            last_boundary[str(row.get("task") or "")] = index

    seen: dict[tuple, int] = {}
    for index, row in enumerate(since_accept):
        task_id = str(row.get("task") or "")
        if row.get("kind") not in ENDINGS or index <= last_boundary.get(task_id, -1):
            continue
        key = ending_signature(row)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] >= REPEAT_LIMIT:
            task, step, why = key
            return str(task or ""), (
                f"{task} ended at {step} the same way {seen[key]} times: {why[:100]} — "
                "the next turn would pay for it again")
    return None


SLICE_AFTER = 2          # two gate failures the same way on one task: re-slice it


def needs_slice(rows: list[dict], task_id: str) -> bool:
    """Two gate failures of the same task, failing the SAME way — same task,
    step and reason, as `spinning` groups an ending — mean the task is wrong,
    not the model: the loop re-slices instead of trying a third time. Two
    different reasons do not trigger this re-slice, but they do not buy the
    task extra tries either: the round cap (REBUILD_ROUNDS) still ends the card
    once its rebuilds run out, whatever the reasons were.

    Only the failures since this card was last dealt with count: a replan, a
    quarantine or a slice that planned (`spends_failures`) answers the failures
    before it, and the card runs on under the same id, so counting them again
    parked a rewritten card on its first new failure. The boundary spends its
    OWN task's failures, as `spinning`'s does.
    """
    boundary = max((index for index, row in enumerate(rows)
                    if row.get("task") == task_id and spends_failures(row)),
                   default=-1)
    endings = [row for row in rows[boundary + 1:]
               if row.get("kind") == "failed" and row.get("step") == "gate"
               and row.get("task") == task_id]
    counts = collections.Counter(ending_signature(row) for row in endings)
    return max(counts.values(), default=0) >= SLICE_AFTER
