"""One door, and nothing passes back out of it.

Split from `throttle.py` at the 200-line cap. "The throttler never raises" is a
SHAPE, not a promise kept call site by call site: every method the driver calls
goes through `_guard`, and so does everything inside it that touches the world
— including the saying of a fault, which is a boundary like any other. The line
that SAID a fault had happened once printed outside the guard around it, which
made a closed stdout the thing that killed the driver.

The host supplies `space` (for the log) and `allow` and `ceiling` (the numbers
the fallback is made of). Nothing here reads a file, a clock or `/proc`.
"""

from __future__ import annotations

from turn_plan import MOST_LANES


def _short(broken) -> str:
    try:
        return repr(broken)[:300]
    except BaseException:   # noqa: BLE001 — even describing it is a boundary
        return "a fault that could not be described"


class Guarded:
    """The door, for a host that has `space`, `allow` and `ceiling`."""

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
