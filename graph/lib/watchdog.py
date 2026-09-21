"""Is the loop busy, or busy going nowhere?

It reads the campaign's own log — no extra wrapper, no second process to keep
alive — and answers three questions the first live campaign taught us to ask:

  spinning     the same task ended the same way twice; the next turn will do it
               again, and pay for the same review again
  stuck        several turns in a row finished nothing; waiting out a usage
               limit or a decision does not count — that is the loop being
               patient, not going nowhere
  futile      hours or answered attempts run on since progress — no work
              accepted, no rebuild queued, no gate passed

Each is a reason to SAY so — once, where the red-flag check shows it — and
carry on; saying it is how anyone sees what happened, never a handoff, because
nothing here waits for a person to read it (CLAUDE.md § Code); only
`stop.flag` stops the campaign. None is something to fix by trying harder.
None of them is measured in money: cost is written into the log because it is
worth reading later, never because it decides anything (the owner, 2026-08-28).
"""

from __future__ import annotations

import dataclasses
import datetime

from watchdog_spin import spinning

TURN_LIMIT = 3            # turns in a row that finish nothing (a turn, not a lane)
ATTEMPT_LIMIT = 12        # answered builder calls since progress
# What that ceiling is NOT about. The plan phase runs before any build in the
# same campaign directory, and its paid slicer calls used to sit in this window:
# one campaign entered its build 29 over a ceiling of 12 and tripped on its
# second card (2026-09-18). The calls say so on themselves, rather than being
# told apart by the task name they happen to carry.
PLANNING = "plan"
IDLE_HOURS = 2.0          # time is the currency: hours since progress


@dataclasses.dataclass
class Verdict:
    spinning: bool = False
    stuck: bool = False
    futile: bool = False
    why: str = ""
    task: str = ""            # the task a spinning verdict is about — never the one that happened to run last

    @property
    def blocked(self) -> bool:
        return self.spinning or self.stuck or self.futile


def check(space, *, attempt_ceiling: int = ATTEMPT_LIMIT,
          hours_ceiling: float = IDLE_HOURS) -> Verdict:
    rows = space.events()
    since_accept = _since_last(rows, "accepted")

    found = spinning(since_accept)
    if found:
        task, why = found
        return Verdict(spinning=True, task=task, why=why)

    # A release that belongs to the accepted turn is not a fruitless turn: the
    # acceptance comes first and its own release follows it.
    # Turns since the last sign of progress, not since the campaign began:
    # accepted work, a queued rebuild, or a passed gate is progress.
    since_progress = _since_last_progress(rows)
    # A TURN, not a lane: three cards released side by side are one turn's work,
    # and counting each of them tripped the ceiling on the loop's first parallel turn.
    # A turn that accepted work is not fruitless, whatever its other lanes did:
    # the turn is the unit, so its id is excluded, not just the accepted task.
    fruitful = {row.get("turn") for row in rows if row.get("kind") == "accepted" and row.get("turn")}
    released = [row for row in since_progress
                if row.get("kind") == "released" and row.get("task") != _last_accepted(rows)
                and row.get("turn") not in fruitful]
    # Lanes of ONE turn share its id and count once; a release without an id is
    # its own turn, as it was when the loop ran a single card at a time.
    turns = len({row["turn"] for row in released if row.get("turn")}) \
        + sum(1 for row in released if not row.get("turn"))
    if turns >= TURN_LIMIT:
        return Verdict(stuck=True, why=(
            f"{turns} turns finished and nothing was accepted; the tasks or their "
            "gates need a person, not another attempt"))

    if hours_ceiling:
        hours = _hours_since_progress(rows)
        if hours >= hours_ceiling:
            return Verdict(futile=True, why=(
                f"{hours:.1f} hours since progress "
                f"(ceiling {hours_ceiling:.0f}h) — time is what this costs"))

    if attempt_ceiling:
        # Same boundary as every window (`_is_progress`): resets on a
        # rebuild_queued or a passed gate too, not only on acceptance.
        answered = sum(1 for row in since_progress
                       if row.get("kind") == "attempt" and row.get("counted")
                       and row.get("purpose") != PLANNING)
        if answered >= attempt_ceiling:
            return Verdict(futile=True, why=(
                f"{answered} answered attempts since progress "
                f"(ceiling {attempt_ceiling}) — the work is not landing"))

    return Verdict()


def _is_progress(row: dict) -> bool:
    """One event that means the campaign actually moved: work accepted, a
    charged rebuild, a task's own gate going green, or cards planned. That last
    is here for the same reason `PLANNING` is: the plan phase runs before the
    build in the same campaign directory, and without it a plan phase that ran
    longer than the hours ceiling handed the build a window that was already
    over it. An answered build call
    is recorded — and counted — before its gate even runs (`loop_steps.py`),
    so it is never enough alone: a loop whose every gate fails still shows
    answered calls. The gate's own step carries the real verdict
    (`loop_judge.py`: `note(passed=...)` on the `"gate"` step) — that is what
    `already_said`, the stuck/turns window, the hours window and the attempt
    ceiling all read, so they agree on what "since progress" means."""
    kind = row.get("kind")
    if kind in ("accepted", "rebuild_queued", "planned"):
        return kind != "rebuild_queued" or row.get("charged") is not False
    return kind == "step" and row.get("step") == "gate" and bool(row.get("passed"))


def already_said(space) -> bool:
    """Whether futility was already said since the last progress event. The
    driver says it once — where the red-flag check shows it — and carries on;
    saying it every turn would be noise, and the log is what a reader reads."""
    rows = space.events()
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        if _is_progress(row):
            return False   # progress: a later stall is said again
        if row.get("kind") == "blocked":
            return True
    return False


def _since_last_progress(rows: list[dict]) -> list[dict]:
    """Everything after the last sign of progress (`_is_progress`)."""
    for index in range(len(rows) - 1, -1, -1):
        if _is_progress(rows[index]):
            return rows[index + 1:]
    return rows


def _stamp(at: str) -> float:
    return datetime.datetime.fromisoformat(str(at).replace("Z", "+00:00")).timestamp()


def _hours_since_progress(rows: list[dict]) -> float:
    """Hours of real work since the last sign of progress — waiting does not count.

    A loop that sits out a usage limit, a hold on a card or a decision being
    made is being patient, not wasteful, so idle and paused stretches are
    subtracted.
    """
    # A queued rebuild is progress too, and so is a task's own gate going
    # green (`_is_progress`): a hard task moving through its rounds, not a
    # loop going through the motions (three rounds of one task once tripped
    # this) — and never the answered call alone, or a loop failing every gate
    # would look busy enough to dodge this ceiling.
    since = rows
    for index in range(len(rows) - 1, -1, -1):
        if _is_progress(rows[index]):
            since = rows[index + 1:]
            break
    # Wall clock, not the sum of the lanes: three lanes of forty minutes are
    # forty minutes of the campaign's time, not two hours of it.
    # Only the part of a span AFTER the last progress counts: a build that started
    # before an acceptance is not time spent going nowhere.
    floor = max((_stamp(row["at"]) for row in rows[:len(rows) - len(since)]
                 if _is_progress(row)), default=None)
    steps = [row for row in since if row.get("kind") == "step" and row.get("seconds")]
    if not steps:
        return 0.0
    spans = sorted((max(_stamp(row["at"]) - float(row["seconds"]), floor or 0.0), _stamp(row["at"]))
                   for row in steps)
    worked, edge = 0.0, None
    for start, end in spans:
        start = max(start, edge) if edge is not None else start
        if end > start:
            worked += end - start
        edge = max(edge or end, end)
    return worked / 3600.0


def _last_accepted(rows: list[dict]) -> str | None:
    for row in reversed(rows):
        if row.get("kind") == "accepted":
            return row.get("task")
    return None


def _since_last(rows: list[dict], kind: str) -> list[dict]:
    for index in range(len(rows) - 1, -1, -1):
        if rows[index].get("kind") == kind:
            return rows[index + 1:]
    return rows
