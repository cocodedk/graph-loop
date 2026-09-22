"""One rule, at the edge, in place of a rule per path.

Any fault at all inside the throttle — making the thing, reading its state,
measuring, stopping the watch, deciding, recording, persisting, printing —
makes the next lane count ONE and the turn it happened in not fresh, so the
turn after it cannot earn an increase from it either.

That replaced "hold at the count you have". Holding needs a count that is
reliably known, and every round of review found another way for the throttle to
believe a number it had not earned; each fix was a new path, and each new path
was a new way to be wrong. There is nothing to work out here: a throttler that
is not sure runs one lane, and climbs again the moment a whole turn goes well.

`BaseException`, because it is the exceptions nobody expects that this is for.
Saying so is a boundary like any other and cannot raise either: the line that
SAID a fault had happened once printed outside the guard around it.

The host supplies `space` (for the log), and takes `allow` and `load` back from
here when a fault lands on it.
"""

from __future__ import annotations

from machine_load import Load
from workspace_claims import _now

ONE = 1                    # what a throttler that is not sure runs
SPOILT = Load(broke=True)  # and what it then knows about the turn: nothing


def _short(broken) -> str:
    try:
        return repr(broken)[:300]
    except BaseException:   # noqa: BLE001 — even describing it is a boundary
        return "a fault that could not be described"


class Guarded:
    """The door, for a host that has `space`, `allow` and `load`."""

    def _outer(self, what: str, run):
        """Everything the driver calls passes here, and nothing passes back out.

        A fault leaves the throttle knowing nothing: one lane next, and a turn
        that cannot be used as evidence for a second.
        """
        try:
            return run()
        except BaseException as broken:   # noqa: BLE001 — the whole point of this file
            self.allow, self.load = ONE, SPOILT
            self._said(what, _short(broken))
            return None

    def _said(self, what: str, why: str) -> None:
        """Say it wherever anything will listen, and never mind what will not."""
        self._tried(lambda: print(f"{_now()} " + (f"  the throttler could not manage {what}: {why}").replace("\n", f"\n{_now()} "), flush=True))
        self._tried(lambda: self.space.event("throttle_fault", what=what, why=why))

    @staticmethod
    def _tried(say) -> None:
        try:
            say()
        except BaseException:   # noqa: BLE001 — a fault nobody can record is not a dead turn
            return
