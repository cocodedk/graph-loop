"""What `--lanes auto` carries between turns, and how it survives a restart.

Split from `throttle.py` at the 200-line cap. The driver is killed and started
again routinely — on new code, by the supervisor, by a person — so everything
the throttler learned lives in one file in the campaign directory, never in the
vault, and is read back by a driver that did not write it.

Which means this file is never trusted. A crash can cut it in half, an older
driver can have written a field this one reads differently, and a person can
edit it. Every value that comes back is made into the type it is read as, or
dropped: the throttler is allowed to hand back a dull answer, never to raise.
"""

from __future__ import annotations

import json
import math
import pathlib

import durable
from machine_load import Load, Sample

STATE = "lanes.json"
FRESH: dict = {"allow": 0, "hold": 0, "ran": 0, "lane_cost_kb": 0.0,
               "gate_ratio": None, "gate_alone": {}, "load": {}}


def _counted(value) -> int:
    """A whole number of lanes or turns, never negative, never a string."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _measured(value) -> float:
    """A positive measurement, or nothing — 0.0 reads as "not measured"."""
    if isinstance(value, bool):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) and number > 0 else 0.0


def _signal(value):
    """A number the decision may compare, or None. A signal this cannot read
    is a signal the machine did not give."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def whole(saved) -> dict:
    """The state, with every field the type this reads it as."""
    state = dict(FRESH)
    if not isinstance(saved, dict):
        return state
    for name in ("allow", "hold", "ran"):
        state[name] = _counted(saved.get(name))
    state["lane_cost_kb"] = _measured(saved.get("lane_cost_kb"))
    state["gate_ratio"] = _measured(saved.get("gate_ratio")) or None
    alone = saved.get("gate_alone")
    state["gate_alone"] = ({str(task): _measured(seconds)
                            for task, seconds in alone.items() if _measured(seconds)}
                           if isinstance(alone, dict) else {})
    state["load"] = saved.get("load") if isinstance(saved.get("load"), dict) else {}
    return state


def as_row(load: Load | None) -> dict:
    """One turn's reading, as fields a log and a state file can hold."""
    if load is None:
        return {}
    row = dict(load._asdict())
    row["baseline"] = dict(load.baseline._asdict())
    return row


def load_of(row) -> Load | None:
    """That reading again, or nothing at all when it cannot be believed."""
    if not isinstance(row, dict) or not row:
        return None
    base = row.get("baseline")
    base = base if isinstance(base, dict) else {}
    fields = {name: _signal(row.get(name)) for name in Load._fields
              if name not in ("baseline", "samples", "broke")}
    return Load(baseline=Sample(**{name: _signal(base.get(name))
                                   for name in Sample._fields}),
                samples=_counted(row.get("samples")),
                broke=bool(row.get("broke")), **fields)


def fields(row) -> dict:
    """A reading as the flat fields the event log holds, or nothing at all."""
    return {} if row is None else {
        name: value for name, value in row._asdict().items()
        if value is not None and value is not False and not hasattr(value, "_asdict")}


def read(path: pathlib.Path) -> dict:
    """The state that file holds, whatever is in it."""
    if not path.exists():
        return dict(FRESH)
    return whole(json.loads(path.read_text("utf-8")))


def write(path: pathlib.Path, state: dict) -> None:
    durable.replace(path, json.dumps(state, sort_keys=True))
