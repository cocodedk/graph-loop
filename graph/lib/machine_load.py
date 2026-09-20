"""What the machine says about itself while a turn runs, and never a raise.

`/proc/meminfo` and `/proc/pressure/{cpu,memory,io}`, sampled every couple of
seconds. Every signal is optional: a platform without pressure stall
information, a container with no `/proc`, a kernel that renames a field — each
reads as nothing at all rather than as an exception. A throttler that kills a
turn is worse than no throttler, and this is the half of it that touches the
outside world.

The aggregate is the one the measurement rig used, so the numbers in
`lanes_auto` mean what they were measured to mean: the lowest MemAvailable
seen, the highest swap in use minus what was in use at the start, and the
highest `some avg10` of each pressure file.
"""

from __future__ import annotations

import threading
from typing import NamedTuple

EVERY = 2.0          # seconds between samples, as the rungs were measured


class Sample(NamedTuple):
    """One reading. `None` is "this machine does not say", never zero."""
    mem_avail_kb: int | None = None
    swap_used_kb: int | None = None
    psi_cpu: float | None = None
    psi_mem: float | None = None
    psi_io: float | None = None


class Load(NamedTuple):
    """A turn's worth of readings, aggregated the way the rungs were."""
    baseline: Sample = Sample()
    mem_avail_min_kb: int | None = None
    swap_growth_kb: int | None = None
    psi_cpu_max: float | None = None
    psi_mem_max: float | None = None
    psi_io_max: float | None = None
    samples: int = 0


def pressure(kind: str) -> float | None:
    """`some avg10` from one pressure file, in percent, or nothing."""
    try:
        with open(f"/proc/pressure/{kind}", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("some"):
                    for field in line.split():
                        if field.startswith("avg10="):
                            return float(field.split("=", 1)[1])
    except (OSError, ValueError):
        return None
    return None


def meminfo() -> dict:
    """The three fields this loop reads, as integers of kB."""
    out: dict[str, int] = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                key, _, rest = line.partition(":")
                if key in ("MemAvailable", "SwapFree", "SwapTotal"):
                    out[key] = int(rest.split()[0])
    except (OSError, ValueError, IndexError):
        return {}
    return out


def read() -> Sample:
    """One reading of everything this loop knows how to ask for."""
    fields = meminfo()
    swap = None
    if "SwapTotal" in fields and "SwapFree" in fields:
        swap = fields["SwapTotal"] - fields["SwapFree"]
    return Sample(fields.get("MemAvailable"), swap,
                  pressure("cpu"), pressure("memory"), pressure("io"))


def _most(values: list) -> float | None:
    seen = [one for one in values if one is not None]
    return max(seen) if seen else None


def _least(values: list) -> int | None:
    seen = [one for one in values if one is not None]
    return min(seen) if seen else None


def gather(samples: list[Sample]) -> Load:
    """The aggregate the decision reads. Growth is measured from the FIRST
    sample — the turn's baseline, taken with no lane running — because an
    absolute number says nothing: swap already in use from yesterday is not
    this turn's doing."""
    if not samples:
        return Load()
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
                samples=len(samples))


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
        self.samples: list[Sample] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.samples = self._one()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="machine-load", daemon=True)
        self._thread.start()

    def _one(self) -> list[Sample]:
        """One reading, or none at all. Never an exception: a machine that will
        not be read is not a reason to end a turn."""
        try:
            return [self.reader()]
        except Exception:   # noqa: BLE001 — a sample nobody could take is not a dead turn
            return []

    def _run(self) -> None:
        while not self._stop.wait(self.every):
            one = self._one()
            if not one:
                return          # it will not start working again inside this turn
            self.samples += one

    def stop(self) -> Load:
        """Stop sampling and hand back what was seen, however little."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.every + 1.0)
            self._thread = None
        return gather(self.samples)
