"""A turn's worth of readings, aggregated — and the one law they answer to.

Split from `machine_load.py` at the 200-line cap: that file watches a turn,
this one says what a turn's readings add up to and whether they are evidence.
The aggregate is the one the measurement rig used, so the numbers in
`lanes_auto` mean what they were measured to mean: the lowest MemAvailable
seen, the highest swap in use minus what was in use at the start, and the
highest `some avg10` of each pressure file.
"""

from __future__ import annotations

import time
from typing import NamedTuple

from machine_read import Sample

MEASURED = 2         # a baseline alone is not a measurement of what the lanes did


def _now() -> float:
    """One clock for every duration. Monotonic, so a machine whose wall clock
    steps backwards cannot make a turn look shorter than it was; the wall clock
    is for log timestamps and nothing else."""
    return time.monotonic()


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
    seconds: float = 0.0      # how long the turn was watched, by the one clock


def fresh(load: Load | None) -> bool:
    """The one law: no fresh evidence, no increase.

    A turn earns another lane only when THIS process measured it in THIS turn —
    two readings at least, each carrying real numbers, taken by a reader that
    started, stayed alive and came back on its own. A thread that never
    started, one that died, one that stalled past its turn, a buffer left over
    from a turn before, a reading read back from a file: none of those is
    evidence, and the decision holds where it is.

    A CUT asks none of this. What a reading saw, it saw, however it ended.
    """
    return (load is not None and not load.broke and not load.carried
            and load.samples >= MEASURED)


def _most(values: list) -> float | None:
    seen = [one for one in values if one is not None]
    return max(seen) if seen else None


def _least(values: list) -> int | None:
    seen = [one for one in values if one is not None]
    return min(seen) if seen else None


def gather(samples: list[Sample], broke: bool = False,
           seconds: float = 0.0) -> Load:
    """The aggregate the decision reads. Growth is measured from the FIRST
    sample — the turn's baseline, taken with no lane running — because an
    absolute number says nothing: swap already in use from yesterday is not
    this turn's doing."""
    if not samples:
        return Load(broke=broke, seconds=seconds)
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
                samples=len(samples), broke=broke, seconds=seconds)
