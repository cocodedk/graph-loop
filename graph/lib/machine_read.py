"""One reading of what the machine says about itself, and never a raise.

Split from `machine_load.py` at the 200-line cap: this is the part that opens
files, `machine_load` is the part that watches a turn. `/proc/meminfo` and
`/proc/pressure/{cpu,memory,io}`. Every signal is optional — a platform without
pressure stall information, a container with no `/proc`, a kernel that renames
a field — and each reads as nothing at all rather than as an exception.
"""

from __future__ import annotations

from typing import NamedTuple


class Sample(NamedTuple):
    """One reading. `None` is "this machine does not say", never zero."""
    mem_avail_kb: int | None = None
    swap_used_kb: int | None = None
    psi_cpu: float | None = None
    psi_mem: float | None = None
    psi_io: float | None = None

    @property
    def whole(self) -> bool:
        """Whether this reading carries what a decision is made of.

        A `/proc` that cannot be read comes back as an EMPTY reading rather
        than as a raise, and counted as a reading it says the machine moved no
        swap — because nobody could look. Memory and swap are the two a
        judgement is made on; the pressure files stay optional, since a
        platform is allowed not to have them.
        """
        return self.mem_avail_kb is not None and self.swap_used_kb is not None


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
