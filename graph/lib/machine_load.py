"""What the machine says about itself while a turn runs, and never a raise.

`machine_read` takes one reading; this watches a turn's worth of them, every
couple of seconds, and aggregates what it saw. A throttler that kills a turn is
worse than no throttler, and this is the half of it that touches the outside
world.

The aggregate is the one the measurement rig used, so the numbers in
`lanes_auto` mean what they were measured to mean: the lowest MemAvailable
seen, the highest swap in use minus what was in use at the start, and the
highest `some avg10` of each pressure file.
"""

from __future__ import annotations

import threading
from typing import NamedTuple

from machine_read import Sample, meminfo, pressure, read  # noqa: F401 — the front door

EVERY = 2.0          # seconds between samples, as the rungs were measured


class Load(NamedTuple):
    """A turn's worth of readings, aggregated the way the rungs were."""
    baseline: Sample = Sample()
    mem_avail_min_kb: int | None = None
    swap_growth_kb: int | None = None
    psi_cpu_max: float | None = None
    psi_mem_max: float | None = None
    psi_io_max: float | None = None
    samples: int = 0
    # Whether a reading failed part way: the samples that were taken are still
    # evidence for a CUT, but a turn nobody could finish watching is never
    # evidence that the machine can take another lane.
    broke: bool = False
    # Whether this came back from a file rather than from this process. Same
    # rule: a cut it earned still stands, another lane is not on offer.
    carried: bool = False


def _most(values: list) -> float | None:
    seen = [one for one in values if one is not None]
    return max(seen) if seen else None


def _least(values: list) -> int | None:
    seen = [one for one in values if one is not None]
    return min(seen) if seen else None


def gather(samples: list[Sample], broke: bool = False) -> Load:
    """The aggregate the decision reads. Growth is measured from the FIRST
    sample — the turn's baseline, taken with no lane running — because an
    absolute number says nothing: swap already in use from yesterday is not
    this turn's doing."""
    if not samples:
        return Load(broke=broke)
    first = samples[0]
    swap = _most([one.swap_used_kb for one in samples])
    return Load(baseline=first,
                mem_avail_min_kb=_least([one.mem_avail_kb for one in samples]),
                swap_growth_kb=(swap - first.swap_used_kb
                                if swap is not None and first.swap_used_kb is not None
                                else None),
                psi_cpu_max=_most([one.psi_cpu for one in samples]),
                psi_mem_max=_most([one.psi_mem for one in samples]),
                psi_io_max=_most([one.psi_io for one in samples]),
                samples=len(samples), broke=broke)


class _Turn:
    """One turn's readings, owned by the thread that fills them.

    A reader can stall past the moment a turn ends. That thread keeps its own
    buffer and its own flag, so a sample it finally takes lands in the turn it
    belongs to and never in the next one — and the next turn starts from
    nothing, not from what a thread nobody is waiting for may still add.
    """

    def __init__(self):
        self.samples: list[Sample] = []
        self.broke = False
        # Its own flag, so a reader that comes back after its turn ended stops
        # then, instead of sampling for ever into a buffer nobody reads.
        self.over = threading.Event()


class Watch:
    """Samples the machine while a turn's lanes run, on a thread of its own.

    A daemon thread, so it can never hold the driver open, and one that
    swallows everything: a sample that fails is a sample that did not happen,
    and a turn nobody could read is an empty `Load` rather than an exception.
    `start` takes the baseline itself, in the caller's thread, so the reading
    with no lane running is the first one whatever the thread does next.
    """

    def __init__(self, every: float = EVERY, reader=read):
        self.every, self.reader = every, reader
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
        turn = _Turn()                  # a fresh buffer: the last turn keeps its own
        turn.samples = self._one()
        turn.broke = not turn.samples
        self.turn = turn
        self._thread = threading.Thread(target=self._run, args=(turn,),
                                        name="machine-load", daemon=True)
        self._thread.start()

    def _one(self) -> list[Sample]:
        """One WHOLE reading, or none at all. Never an exception: a machine
        that will not be read is not a reason to end a turn, and a reading with
        nothing in it is not a reading."""
        try:
            one = self.reader()
        except Exception:   # noqa: BLE001 — a sample nobody could take is not a dead turn
            return []
        return [one] if getattr(one, "whole", False) else []

    def _run(self, turn: _Turn) -> None:
        while not turn.over.wait(self.every):
            one = self._one()
            if not one:
                # It will not start working again inside this turn, and the
                # turn must not read as a quiet one for want of a reading.
                turn.broke = True
                return
            turn.samples.append(one[0])

    def stop(self) -> Load:
        """Stop sampling and hand back what was seen, however little."""
        turn, thread = self.turn, self._thread
        turn.over.set()
        if thread is not None:
            thread.join(timeout=self.every + 1.0)
            if thread.is_alive():
                # Still inside a read. What it eventually returns belongs to
                # this turn's buffer, which nothing reads again, and a turn
                # whose reader never came back is not a measured one.
                turn.broke = True
                self._stalled.append(thread)
            self._thread = None
        return gather(list(turn.samples), turn.broke)
