"""What the machine says about itself while a turn runs, and never a raise.

`machine_read` takes one reading, `machine_gather` says what a turn's worth of
them add up to, and this watches a turn: one thread, one bounded wait for the
baseline, one buffer per turn. A throttler that kills a turn is worse than no
throttler, and this is the half of it that touches the outside world.

The aggregate is the one the measurement rig used, so the numbers in
`lanes_auto` mean what they were measured to mean: the lowest MemAvailable
seen, the highest swap in use minus what was in use at the start, and the
highest `some avg10` of each pressure file.
"""

from __future__ import annotations

import threading

from machine_gather import (  # noqa: F401 — this module is the front door for all of it
    MEASURED,
    Load,
    _now,
    fresh,
    gather,
)
from machine_read import Sample, meminfo, pressure, read  # noqa: F401 — the front door

EVERY = 2.0          # seconds between samples, as the rungs were measured
OPENING = 3.0        # how long a turn waits for its first reading, and no longer


class _Turn:
    """One turn's readings, owned by the thread that fills them.

    A reader can stall past the moment a turn ends. That thread keeps its own
    buffer, its own flags and its own stop, so a sample it finally takes lands
    in the turn it belongs to and never in the next one — and the next turn
    starts from nothing, not from what a thread nobody is waiting for may add.

    `finished` is the thread's own word that it stopped because it was asked
    to. Nothing else sets it, so every other ending — a fault, a partial
    reading, a stall, a thread that never ran — leaves the turn unproven.
    """

    def __init__(self):
        self.samples: list[Sample] = []
        self.broke = False
        self.finished = False
        self.started = 0.0
        self.over = threading.Event()      # this turn's own stop, never the next one's
        self.opened = threading.Event()    # the baseline has landed, or never will


class Watch:
    """Samples the machine while a turn's lanes run, on a thread of its own.

    A daemon thread, so it can never hold the driver open, and one that
    swallows everything: a sample that fails is a sample that did not happen,
    and a turn nobody could read is an empty `Load` rather than an exception.

    The baseline is taken BY that thread rather than by the caller, and `start`
    waits a bounded time for it: a `/proc` read that never returns then costs
    one turn's evidence instead of the driver.
    """

    def __init__(self, every: float = EVERY, reader=None, opening: float = OPENING):
        self.every, self.reader, self.opening = every, reader, opening
        self.turn = _Turn()
        self._thread: threading.Thread | None = None
        self._stalled: list[threading.Thread] = []   # kept referenced, never reused

    @property
    def samples(self) -> list[Sample]:
        return self.turn.samples

    @property
    def broke(self) -> bool:
        return self.turn.broke

    def start(self) -> None:
        """Begin this turn's readings, and never block on a reader that will
        not come back.

        The buffer is cleared FIRST: whatever fails after this line — the
        thread, the clock, the reader — the turn that follows carries nothing
        from the turn before it, and `stop` calls it unproven.
        """
        self.turn, self._thread = _Turn(), None
        turn = self.turn
        turn.started = _now()
        thread = threading.Thread(target=self._run, args=(turn,),
                                  name="machine-load", daemon=True)
        thread.start()
        self._thread = thread
        turn.opened.wait(self.opening)

    def _one(self) -> list[Sample]:
        """One WHOLE reading, or none at all.

        The reader is looked up when it is CALLED, not captured when this was
        made: bound as a default argument it could not be replaced, and a test
        that patched the reading was patching something nothing would call.
        """
        try:
            one = (self.reader or read)()
        except BaseException:   # noqa: BLE001 — SystemExit in a reader is not an increase either
            return []
        return [one] if getattr(one, "whole", False) else []

    def _run(self, turn: _Turn) -> None:
        """The baseline at once, then one reading every `every`, until asked."""
        try:
            while not turn.over.wait(self.every if turn.samples else 0):
                one = self._one()
                if not one:
                    # It will not start working again inside this turn, and the
                    # turn must not read as a quiet one for want of a reading.
                    turn.broke = True
                    return
                turn.samples.append(one[0])
                turn.opened.set()
            turn.finished = True        # asked to stop, and it stopped
        except BaseException:   # noqa: BLE001 — a thread that dies leaves a turn nobody proved
            turn.broke = True
        finally:
            turn.opened.set()           # never leave `start` waiting on a dead thread

    def stop(self) -> Load:
        """Stop sampling and hand back what was seen, however little."""
        turn, thread = self.turn, self._thread
        turn.over.set()
        if thread is None:
            turn.broke = True           # it never started: there is no turn to believe
        else:
            thread.join(timeout=self.every + 1.0)
            if thread.is_alive():
                # Still inside a read. What it eventually returns belongs to
                # this turn's buffer, which nothing reads again.
                turn.broke = True
                self._stalled.append(thread)
            self._thread = None
        if not turn.finished:
            turn.broke = True           # it did not come back on its own
        return gather(list(turn.samples), turn.broke,
                      round(_now() - turn.started, 3) if turn.started else 0.0)
