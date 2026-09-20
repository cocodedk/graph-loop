"""`--lanes auto` wired to a campaign, and the one rule it keeps: it never
raises into the loop.

A throttler that kills a turn is worse than no throttler, so every path here
is wrapped: a `/proc` that is not there, a state file a crash cut in half, an
event nobody could write. Each of those returns the last safe value and says
what happened, in the log where everything else this loop does is said.

What it carries between turns lives in the campaign directory — `lanes.json`,
beside the events — never in the vault, which is the backlog a person reads.
A driver restarted on new code picks that file up and carries on from the
allowance the last one had proved.

The decision itself is `lanes_auto.decide`, which is pure and takes numbers.
This is only the part that reads a machine, keeps the state and writes it down.
"""

from __future__ import annotations

import json

import durable
import lanes_auto
from lanes_auto import AUTO, LANE_COST_KB
from machine_load import Watch
from turn_plan import MOST_LANES

STATE = "lanes.json"
FRESH = {"allow": 0, "hold": 0, "ran": 0, "lane_cost_kb": 0.0,
         "gate_ratio": None, "gate_alone": {}}


class Throttle:
    """The driver holds one of these for the length of a run.

    `opens` before the lanes, `lanes` to ask how many, `closes` once they are
    done. With anything but `--lanes auto` — and in a dry run, which writes
    nothing — every one of them does nothing at all: no reading, no file, no
    event, so a campaign that never asked for this cannot be changed by it.
    """

    def __init__(self, space, args, watch=None):
        self.space = space
        self.on = (getattr(args, "lanes", None) == AUTO
                   and not getattr(args, "dry_run", False))
        self.ceiling = max(0, int(getattr(args, "lanes_max", 0) or 0))
        self.watch = watch or Watch()
        self.load = None
        self.state = dict(FRESH)
        if not self.on:
            return
        self._quiet("reading its state", self._load)
        if self.ceiling > MOST_LANES:
            # Said once, out loud: three is the keeper's own limit — it gives
            # up after three rebuilds of a branch that moved under it — so a
            # higher ceiling is taken as three rather than quietly obeyed.
            print(f"--lanes-max {self.ceiling} is above the keeper's "
                  f"{MOST_LANES}: taking {MOST_LANES}")
            self._quiet("saying so", lambda: self.space.event(
                "lanes_ceiling_lowered", asked=self.ceiling, most=MOST_LANES))

    # ------------------------------------------------------------- the driver

    def opens(self) -> None:
        """Start reading the machine, with no lane running: this first sample
        is the baseline every judgement is a rise over."""
        if self.on:
            self._quiet("starting to read the machine", self.watch.start)

    def lanes(self, width: int) -> int:
        """How many lanes this turn, or 0 when nothing asked for `auto`."""
        if not self.on:
            return 0
        return self._quiet("deciding", lambda: self._decide(width), self._safe(width))

    def closes(self, turn_id: str = "", ran: int = 0) -> None:
        """Read what the turn did to the machine, and keep it for the next."""
        if self.on:
            self._quiet("reading what the turn cost", lambda: self._close(turn_id, ran))

    # --------------------------------------------------------------- the work

    def _decide(self, width: int) -> int:
        out = lanes_auto.decide(
            width=width, ceiling=self.ceiling, most=MOST_LANES,
            allow=int(self.state.get("allow") or 0),
            ran=int(self.state.get("ran") or 0),
            hold=int(self.state.get("hold") or 0), load=self.load,
            lane_cost_kb=float(self.state.get("lane_cost_kb") or LANE_COST_KB),
            gate_ratio=self.state.get("gate_ratio"))
        self.state.update(allow=out.allow, hold=out.hold)
        self._quiet("keeping its state", self._save)
        self._quiet("writing the decision down",
                    lambda: self.space.event(
                        "lanes_decided", width=width, lanes=out.lanes,
                        allow=out.allow, lanes_max=self.ceiling, most=MOST_LANES,
                        move=out.move, why=out.why,
                        baseline=_fields(getattr(self.load, "baseline", None)),
                        signals=_fields(self.load),
                        gate_ratio=self.state.get("gate_ratio"),
                        lane_cost_kb=self.state.get("lane_cost_kb") or None))
        print(f"  lanes: {out.lanes} — {out.why}")
        return out.lanes

    def _close(self, turn_id: str, ran: int) -> None:
        self.load = self.watch.stop()
        if not self.load.samples:
            # Never read, so never judged: the decision falls back on what the
            # machine was already judged to take, and says here that it did.
            self._fault("reading the machine", "nothing could be read this turn")
        self.state["ran"] = ran
        self.state["gate_ratio"] = self._gate_ratio(turn_id, ran)
        if not self.state.get("lane_cost_kb"):
            # The first turn that actually shows a drop, and only it: later the
            # machine is carrying whatever the campaign has built up, and the
            # drop is no longer one lane's own cost. Until then the assumed
            # 2.5 GB stands.
            self.state["lane_cost_kb"] = lanes_auto.lane_cost(self.load, ran) or 0.0
        self._quiet("keeping its state", self._save)

    def _gate_ratio(self, turn_id: str, ran: int) -> float | None:
        """The worst gate of this turn against the same card's gate run alone.

        A gate is the one step whose wall time means something across turns,
        and only against ITSELF: two cards' gates are two different programs.
        A turn that ran one lane is what teaches the lone time.
        """
        alone = dict(self.state.get("gate_alone") or {})
        worst = None
        for row in self.space.events():
            if row.get("kind") != "step" or row.get("step") != "gate":
                continue
            if turn_id and row.get("turn") != turn_id:
                continue
            task, seconds = str(row.get("task") or ""), float(row.get("seconds") or 0)
            if seconds <= 0:
                continue
            if ran <= 1:
                alone[task] = seconds
            elif alone.get(task):
                worst = max(worst or 0.0, seconds / alone[task])
        self.state["gate_alone"] = alone
        return worst

    # -------------------------------------------------------------- the files

    @property
    def path(self):
        return self.space.root / STATE

    def _load(self) -> None:
        if self.path.exists():
            self.state = {**FRESH, **json.loads(self.path.read_text("utf-8"))}

    def _save(self) -> None:
        durable.replace(self.path, json.dumps(self.state, sort_keys=True))

    def _safe(self, width: int) -> int:
        """The last value known to be safe: what the machine was already
        judged to take, never more than there are cards."""
        return max(1, min(int(self.state.get("allow") or 1), MOST_LANES, max(1, width)))

    def _quiet(self, what: str, run, fallback=None):
        try:
            return run()
        except Exception as broken:   # noqa: BLE001 — a dead turn is worse than a dumb throttler
            self._fault(what, repr(broken)[:300])
            return fallback

    def _fault(self, what: str, why: str) -> None:
        print(f"  the throttler could not manage {what}: {why}")
        try:
            self.space.event("throttle_fault", what=what, why=why)
        except Exception:   # noqa: BLE001, S110 — a record nobody can write is not a dead turn either
            pass


def _fields(row) -> dict:
    """A reading as plain fields the log can hold, or nothing."""
    return {} if row is None else {
        name: value for name, value in row._asdict().items()
        if value is not None and not hasattr(value, "_asdict")}
