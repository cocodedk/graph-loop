"""`--lanes auto`: how many lanes this turn, decided from the machine.

One pure function over numbers. Everything it needs is handed to it — the
frontier's width, the owner's ceiling, what the last turn was allowed, what the
machine did while that turn ran — so the decision is a table a test can state
and nothing here can fail on a missing file.

The numbers were measured on one real machine, on a ladder of one, two and
three lanes of the same gate:

- Swap is the criterion that fired. Three lanes moved 1.1–1.3 GB of swap while
  every gate still passed; two moved 414 MB; one moved none.
- An idle machine sat at 88–94 % io pressure and was LOWER under load, so io is
  recorded and never cut on: an absolute threshold would have throttled this
  machine to one lane for ever. Every judgement here is a RISE over the
  baseline read at that turn's start, with no lane running.
- One lane's own cost, from the first turn's drop in MemAvailable, was about
  2.6 GB. Until a turn says otherwise, a lane is assumed to cost 2.5 GB.
"""

from __future__ import annotations

from typing import NamedTuple

from machine_load import Load
from turn_plan import MOST_LANES

AUTO = "auto"                      # what `--lanes auto` passes through argparse
MB = 1024                          # kB in a MB, as /proc counts them
GB = 1024 * 1024

SWAP_CUT_KB = 500 * MB             # more swap than this in one turn: halve
SWAP_QUIET_KB = 64 * MB            # below this the machine never reached for disk
PRESSURE_CUT = 20.0                # points of `some avg10` over the turn's baseline
GATE_CUT = 2.5                     # a gate this much slower than its time alone
RESERVE_KB = 3 * GB                # memory the loop leaves to the machine
LANE_COST_KB = 2.5 * GB            # one lane's cost, until a turn measures it
HOLD_TURNS = 2                     # no increase for this many turns after a cut


class Decision(NamedTuple):
    """What this turn runs, what the machine is judged to take, and why."""
    lanes: int
    allow: int
    why: str
    move: str = "same"
    hold: int = 0


def _mb(kb: float) -> str:
    return f"{kb / MB:.0f} MB"


def _gb(kb: float) -> str:
    return f"{kb / GB:.1f} GB"


def _rise(most: float | None, base: float | None) -> float | None:
    return None if most is None or base is None else most - base


def cut_reason(load: Load | None, gate_ratio: float | None = None) -> str:
    """Why this turn says halve, in words, or nothing at all."""
    if load is not None:
        if load.swap_growth_kb is not None and load.swap_growth_kb > SWAP_CUT_KB:
            return (f"swap grew {_mb(load.swap_growth_kb)} inside the turn, "
                    f"past the {_mb(SWAP_CUT_KB)} this machine was measured to "
                    "take badly")
        for name, now, base in (("memory", load.psi_mem_max, load.baseline.psi_mem),
                                ("cpu", load.psi_cpu_max, load.baseline.psi_cpu)):
            climbed = _rise(now, base)
            if climbed is not None and climbed > PRESSURE_CUT:
                return (f"{name} pressure rose {climbed:.0f} points over this "
                        f"turn's baseline of {base:.0f}")
    if gate_ratio is not None and gate_ratio > GATE_CUT:
        return f"a gate took {gate_ratio:.1f} times its time alone"
    return ""


def _clean(load: Load | None, gate_ratio: float | None) -> bool:
    """A turn that earns another lane.

    Nothing complained, AND swap barely moved: the rung that moved 414 MB was
    one below the rung that had to be halved, so a machine already reaching for
    disk is not one to ask more of. A turn that measured nothing at all is not
    clean either — a lane is never added on no evidence.
    """
    if cut_reason(load, gate_ratio):
        return False
    if load is None or load.swap_growth_kb is None:
        return False
    return load.swap_growth_kb <= SWAP_QUIET_KB


def decide(*, width: int, ceiling: int = 0, most: int = MOST_LANES, allow: int = 0,
           ran: int = 0, hold: int = 0, load: Load | None = None,
           lane_cost_kb: float = LANE_COST_KB,
           gate_ratio: float | None = None) -> Decision:
    """This turn's lanes, from last turn's allowance and what the machine did.

    `allow` is what the machine is judged to take and is what climbs or is
    halved; `lanes` is that, narrowed to the cards there actually are. The two
    are kept apart so a turn with one startable card does not reset a ceiling
    that three turns of evidence bought.
    """
    room = max(1, min(width, most, ceiling or most))
    if allow < 1:                       # the first turn this campaign decides
        if ceiling:
            opening = max(1, min(ceiling, most))
            return Decision(min(opening, max(1, width)), opening,
                            f"first turn: starting at the ceiling of {opening} "
                            "rather than serialising cards the graph calls "
                            "independent", "start")
        return Decision(1, 1, "first turn: no ceiling was given, so it starts at "
                              "one lane and adds one per clean turn", "start")
    allow = min(allow, most, ceiling or most)
    why = cut_reason(load, gate_ratio)
    if why:
        cut = max(1, allow // 2)
        return Decision(min(cut, max(1, width)), cut,
                        f"{why} — halving {allow} to {cut}", "cut", HOLD_TURNS)
    if hold > 0:
        return Decision(min(allow, room), allow,
                        f"holding still: {hold} turn(s) to go after a cut",
                        "hold", hold - 1)
    if allow >= min(most, ceiling or most):
        return Decision(min(allow, room), allow,
                        f"already at the ceiling of {allow}", "same")
    if not _clean(load, gate_ratio):
        moved = "" if load is None or load.swap_growth_kb is None else \
            f" (swap moved {_mb(load.swap_growth_kb)})"
        return Decision(min(allow, room), allow,
                        f"not a clean turn{moved}: staying at {allow}", "hold")
    if ran and ran < allow:
        return Decision(min(allow, room), allow,
                        f"only {ran} of {allow} lanes ran, so nothing was learned "
                        "about another", "hold")
    spare = None if load is None or load.mem_avail_min_kb is None else \
        load.mem_avail_min_kb - RESERVE_KB
    if spare is not None and spare < lane_cost_kb:
        return Decision(min(allow, room), allow,
                        f"{_gb(max(0, spare))} spare over the {_gb(RESERVE_KB)} "
                        f"reserve, and a lane costs {_gb(lane_cost_kb)}: "
                        f"staying at {allow}", "hold")
    grown = min(allow + 1, most, ceiling or most)
    return Decision(min(grown, max(1, width)), grown,
                    f"a clean turn at {allow}: one more lane", "add")


def lane_cost(load: Load | None, ran: int) -> float | None:
    """What one lane cost this turn, from the drop in MemAvailable, or nothing.

    The first turn's drop is what the reserve rule is measured against; a later
    turn does not re-measure it, because by then the machine is carrying
    whatever the campaign has built up and the drop is no longer one lane's.
    """
    if load is None or ran < 1:
        return None
    base, low = load.baseline.mem_avail_kb, load.mem_avail_min_kb
    if base is None or low is None or base <= low:
        return None
    return (base - low) / ran
