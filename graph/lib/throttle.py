"""`--lanes auto` wired to a campaign, under one rule at its edge.

Any fault anywhere in here makes the next lane count ONE and the turn it
happened in not fresh — `throttle_guard` is that rule, and the four things the
driver calls are the only doors into this. There is no second rule and no
per-path recovery: a throttler that is not sure runs one lane, and climbs again
the moment a whole turn goes well.

Everything else it does is ordered so that doubt resolves downward. A CUT is
adopted before it is written down, so nothing can keep it from landing. An
INCREASE is the last thing that happens, after the log entry and the state file
are on the platter, so nothing that failed can leave a raised count behind. And
what comes back from that file may carry a cut forward but never a reason to
climb, because the turn that measured it was run by a process that is gone.

The decision itself is `lanes_auto.decide`, which is pure and takes numbers.
What it carries between turns is `throttle_state`, and the one signal read from
the campaign's own history is `throttle_gates`.
"""

from __future__ import annotations

import lanes_auto
import throttle_gates
import throttle_state
from lanes_auto import AUTO, LANE_COST_KB
from machine_load import Watch
from throttle_guard import ONE, Guarded
from throttle_state import STATE  # the campaign file both of them name
from turn_plan import MOST_LANES
from workspace_claims import _now


class Throttle(Guarded):
    """The driver holds one of these for the length of a run.

    `opens` before the lanes, `lanes` to ask how many, `closes` once they are
    done. With anything but `--lanes auto` — and in a dry run, which writes
    nothing — every one of them does nothing at all: no reading, no file, no
    event, so a campaign that never asked for this cannot be changed by it, and
    a fault in here cannot reach it either.
    """

    def __init__(self, space, args, watch=None):
        # Nothing before the rule may fail. Reading the arguments, making the
        # watch and reading the state file all can — a Watch that could not be
        # built used to escape `Throttle(...)` even in numeric mode — so they
        # happen behind it, and `on` stays False until they have.
        self.space = space
        self.on = False
        self.ceiling = 0
        self.watch = watch
        self.load = None
        self.state = dict(throttle_state.FRESH)
        self.allow = 0
        self._outer("making itself ready", lambda: self._ready(args))

    # ------------------------------------------------------------- the driver

    def opens(self) -> None:
        """Start reading the machine, with no lane running: this first sample
        is the baseline every judgement is a rise over."""
        if self.on:
            self._outer("starting to read the machine", self.watch.start)

    def lanes(self, width: int) -> int:
        """How many lanes this turn, or 0 when nothing asked for `auto`."""
        if not self.on:
            return 0
        chosen = self._outer("deciding this turn's lanes", lambda: self._decide(width))
        return chosen if isinstance(chosen, int) and chosen >= ONE else ONE

    def closes(self, turn_id: str = "", ran: int = 0) -> None:
        """Read what the turn did to the machine, and keep it for the next."""
        if self.on:
            self._outer("reading what the turn cost", lambda: self._close(turn_id, ran))

    # --------------------------------------------------------------- the work

    def _ready(self, args) -> None:
        self.on = (getattr(args, "lanes", None) == AUTO
                   and not getattr(args, "dry_run", False))
        self.ceiling = max(0, int(getattr(args, "lanes_max", 0) or 0))
        if self.watch is None:
            self.watch = Watch()
        if not self.on:
            return
        self.state = throttle_state.read(self.path)
        self.allow = max(0, int(self.state.get("allow") or 0))
        kept = throttle_state.load_of(self.state.get("load"))
        # CARRIED: a reading made by a process that is gone. It may still cut —
        # what it saw, it saw — but it is not proof that this machine will take
        # another lane, so the first decision after a restart cannot climb.
        self.load = None if kept is None else kept._replace(carried=True)
        if self.ceiling > MOST_LANES:
            # Said once, out loud: three is the keeper's own limit — it gives
            # up after three rebuilds of a branch that moved under it — so a
            # higher ceiling is taken as three rather than quietly obeyed.
            print(f"{_now()} " + (f"--lanes-max {self.ceiling} is above the keeper's "
                  f"{MOST_LANES}: taking {MOST_LANES}").replace("\n", f"\n{_now()} "), flush=True)
            self.space.event("lanes_ceiling_lowered", asked=self.ceiling,
                             most=MOST_LANES)

    def _decide(self, width: int) -> int:
        """The candidate decision, and then — for an INCREASE, and only for an
        increase — every step of granting it, before it is granted.

        Holding costs nothing. Raising the count does, because the next driver
        runs on what was written down, so the raised number is adopted last,
        after the log entry and the state file are on the platter. A CUT is the
        other way round: adopted at once, written afterwards. Either way a
        failure anywhere in here is one fault like any other, and the rule at
        the edge answers it with one lane.
        """
        out = lanes_auto.decide(
            width=int(width), ceiling=self.ceiling, most=MOST_LANES, allow=self.allow,
            ran=int(self.state.get("ran") or 0),
            hold=int(self.state.get("hold") or 0), load=self.load,
            lane_cost_kb=float(self.state.get("lane_cost_kb") or LANE_COST_KB),
            gate_ratio=self.state.get("gate_ratio"))
        raised = {**self.state, "allow": out.allow, "hold": out.hold}
        if out.allow > self.allow:
            self._record(width, out)                    # said, then kept, then held
            throttle_state.write(self.path, raised)
            self.allow, self.state = out.allow, raised
        else:
            self.allow, self.state = out.allow, raised
            self._record(width, out)
            self._save()
        print(f"{_now()} " + (f"  lanes: {out.lanes} — {out.why}").replace("\n", f"\n{_now()} "), flush=True)
        return out.lanes

    def _record(self, width: int, out) -> None:
        self.space.event(
            "lanes_decided", width=width, lanes=out.lanes, allow=out.allow,
            lanes_max=self.ceiling, most=MOST_LANES, move=out.move, why=out.why,
            baseline=throttle_state.fields(getattr(self.load, "baseline", None)),
            signals=throttle_state.fields(self.load),
            gate_ratio=self.state.get("gate_ratio"),
            lane_cost_kb=self.state.get("lane_cost_kb") or None)

    def _close(self, turn_id: str, ran: int) -> None:
        self.load = self.watch.stop()
        if not self.load.samples:
            self._said("reading the machine", "nothing could be read this turn")
        self.state["ran"] = max(0, int(ran))
        self.state["load"] = throttle_state.as_row(self.load)
        if not self.state.get("lane_cost_kb"):
            # The first turn that actually shows a drop, and only it: later the
            # machine is carrying whatever the campaign has built up, and the
            # drop is no longer one lane's own cost. Until then 2.5 GB stands.
            self.state["lane_cost_kb"] = lanes_auto.lane_cost(self.load, ran) or 0.0
        # The machine's reading goes on the platter BEFORE anything else that
        # can fail: it is the only reason the next driver can cut, and the gate
        # timing below is a nicety that once took it down with it.
        self._save()
        self.state["gate_ratio"] = self._gate_ratio(turn_id, ran)
        self._save()

    def _gate_ratio(self, turn_id: str, ran: int) -> float | None:
        """This turn's worst gate against its own lone time (`throttle_gates`)."""
        return throttle_gates.ratio(self.space, self.state, turn_id, ran)

    # -------------------------------------------------------------- the files

    @property
    def path(self):
        return self.space.root / STATE

    def _save(self) -> None:
        throttle_state.write(self.path, self.state)
