"""A call that does nothing is stopped: the idle limit of `runner.run`, split out at the 200-line cap."""

from __future__ import annotations

import os
import pathlib
import subprocess
import time

IDLE_POLL = 5   # seconds between looks at a call that has an idle limit


class Idle(subprocess.TimeoutExpired):
    """A call that sat alone in its group, using almost no CPU, for its whole idle limit."""


def _group_ticks(pgid: int) -> tuple[int, int]:
    """How many processes the group has and the CPU ticks they have used. ponytail: Linux's /proc; where
    there is none the group looks empty and the idle limit never fires, upgrade path a psutil call."""
    members = ticks = 0
    for entry in os.listdir("/proc"):
        try:
            fields = pathlib.Path(f"/proc/{entry}/stat").read_text().rpartition(")")[2].split()
        except OSError:   # not a process, or gone since the listing
            continue
        if int(fields[2]) == pgid:
            members, ticks = members + 1, ticks + int(fields[11]) + int(fields[12])
    return members, ticks


def _wait(proc: subprocess.Popen, stdin: str, timeout: float, idle: float) -> tuple[str, str]:
    """`proc.communicate`; with an `idle` limit, a call that is alone in its group and has used less than
    `idle` ticks of CPU (1% of a core) in `idle` seconds raises `Idle`. A child running under it (a gate, a
    tool) or any real CPU opens a new window. Under a driver turn the owner process is a second member."""
    if not idle:
        return proc.communicate(input=stdin, timeout=timeout)
    start = window = time.monotonic()
    ticks, send = _group_ticks(proc.pid)[1], stdin
    while True:
        try:
            return proc.communicate(input=send, timeout=IDLE_POLL)
        except subprocess.TimeoutExpired:
            send = None
        now = time.monotonic()
        if now - start >= timeout:
            raise subprocess.TimeoutExpired(proc.args, timeout) from None
        if now - window >= idle:
            members, used = _group_ticks(proc.pid)
            if members <= 1 and used - ticks < idle:
                raise Idle(proc.args, idle) from None
            window, ticks = now, used
