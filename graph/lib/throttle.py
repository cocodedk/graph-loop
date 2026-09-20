"""`--lanes auto` wired to a campaign, and the one rule it keeps: it never
raises into the loop.

That rule is a SHAPE here, not a promise made call site by call site. Every
method the driver calls goes through one door, `_guard`, which catches
everything — a `/proc` that is not there, a state file a crash cut in half, a
log nobody can write, a stdout that is closed — and answers from `_floor`,
which is arithmetic over numbers already in memory and touches nothing at all.
Saying that a fault happened is a boundary like any other and is wrapped the
same way: the line that SAID so used to print outside the guard around it, so a
broken stdout made every recorded fault the thing that killed the driver.

The second rule is that a lane is ADDED only on positive proof, and doubt
always resolves downward. What comes back from the state file may carry a
pending cut and the learned cost of a lane; it is never evidence that this
machine will take another one, because the turn that measured it was run by a
process that is gone.

The decision itself is `lanes_auto.decide`, which is pure and takes numbers.
What it carries between turns is `throttle_state`, and the one signal read from
the campaign's own history is `throttle_gates`.
"""

from __future__ import annotations

import lanes_auto
import throttle_gates
import throttle_state
from lanes_auto import AUTO, LANE_COST_KB
from machine_load import Load, Watch
from throttle_state import STATE  # the campaign file both of them name
from turn_plan import MOST_LANES


def _short(broken) -> str:
    try:
        return repr(broken)[:300]
    except BaseException:   # noqa: BLE001 — even describing it is a boundary
        return "a fault that could not be described"


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
        self.load: Load | None = None
        self.state = dict(throttle_state.FRESH)
        self.allow = 0            # the last safe number, in memory, always an int
        if self.on:
            self._guard("reading its state", self._open)

    # ------------------------------------------------------------- the driver

    def opens(self) -> None:
        """Start reading the machine, with no lane running: this first sample
        is the baseline every judgement is a rise over."""
        if self.on:
            self._guard("starting to read the machine", self.watch.start)

    def lanes(self, width: int) -> int:
        """How many lanes this turn, or 0 when nothing asked for `auto`."""
        if not self.on:
            return 0
        return self._guard("deciding this turn's lanes",
                           lambda: self._decide(width), lambda: self._floor(width))

    def closes(self, turn_id: str = "", ran: int = 0) -> None:
        """Read what the turn did to the machine, and keep it for the next."""
        if self.on:
            self._guard("reading what the turn cost", lambda: self._close(turn_id, ran))

    # -------------------------------------------------------------- the door

    def _guard(self, what: str, run, fallback=None):
        """Everything the driver calls passes here, and nothing passes back out.

        The fallback is a callable, worked out INSIDE this frame: computed as
        an argument it ran outside the guard, and a state file holding
        `{"allow": "bad"}` then killed the driver on every restart.
        """
        try:
            return run()
        except BaseException as broken:   # noqa: BLE001 — a dead turn is worse than a dumb throttler
            why = _short(broken)
        self._said(what, why)
        if fallback is None:
            return None
        try:
            return fallback()
        except BaseException:   # noqa: BLE001 — `_floor` cannot fail; if it did, one lane
            return 1

    def _said(self, what: str, why: str) -> None:
        """Say it wherever anything will listen, and never mind what will not."""
        self._tried(lambda: print(f"  the throttler could not manage {what}: {why}"))
        self._tried(lambda: self.space.event("throttle_fault", what=what, why=why))

    @staticmethod
    def _tried(say) -> None:
        try:
            say()
        except BaseException:   # noqa: BLE001 — a fault nobody can record is not a dead turn
            return

    def _floor(self, width) -> int:
        """The last value known to be safe. Arithmetic over numbers already in
        memory: no file, no `/proc`, no log, nothing that can fail — because
        this is the only path to an answer once everything else has."""
        try:
            return max(1, min(int(self.allow) or 1, int(self.ceiling) or MOST_LANES,
                              MOST_LANES, max(1, int(width))))
        except BaseException:   # noqa: BLE001 — a number this cannot make is one lane
            return 1

    # --------------------------------------------------------------- the work

    def _open(self) -> None:
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
            print(f"--lanes-max {self.ceiling} is above the keeper's "
                  f"{MOST_LANES}: taking {MOST_LANES}")
            self.space.event("lanes_ceiling_lowered", asked=self.ceiling,
                             most=MOST_LANES)

    def _decide(self, width: int) -> int:
        out = lanes_auto.decide(
            width=int(width), ceiling=self.ceiling, most=MOST_LANES, allow=self.allow,
            ran=int(self.state.get("ran") or 0),
            hold=int(self.state.get("hold") or 0), load=self.load,
            lane_cost_kb=float(self.state.get("lane_cost_kb") or LANE_COST_KB),
            gate_ratio=self.state.get("gate_ratio"))
        self.allow = out.allow                 # in memory first: the fallback reads it
        self.state.update(allow=out.allow, hold=out.hold)
        self._guard("keeping its state", self._save)
        self._guard("writing the decision down", lambda: self._record(width, out))
        self._guard("saying so", lambda: print(f"  lanes: {out.lanes} — {out.why}"))
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
        self.load = self._guard("reading the machine", self.watch.stop,
                                lambda: Load(broke=True))
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
        self._guard("keeping its state", self._save)
        self.state["gate_ratio"] = self._guard(
            "timing this turn's gates", lambda: self._gate_ratio(turn_id, ran))
        self._guard("keeping its state", self._save)

    def _gate_ratio(self, turn_id: str, ran: int) -> float | None:
        """This turn's worst gate against its own lone time (`throttle_gates`)."""
        return throttle_gates.ratio(self.space, self.state, turn_id, ran)

    # -------------------------------------------------------------- the files

    @property
    def path(self):
        return self.space.root / STATE

    def _save(self) -> None:
        throttle_state.write(self.path, self.state)
