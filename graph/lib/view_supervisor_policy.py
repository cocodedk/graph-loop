"""The board's mirror of `supervisor.sh`, read from its own log: how long a
restart may take, and which supervisor generation wrote the log. Split from
`view_health` at the 200-line cap; that module re-exports these names. The
`view` prefix matters: `code_is_newer` restarts the driver on any non-view
module changing, and this one is read by the board alone."""

from __future__ import annotations

SLACK_SECONDS = 60   # on top of the supervisor's own pause before it is a fault


def restart_grace(log_lines: list[str], restart_aware: bool | None = None) -> float:
    """How long the supervisor may take to restart the driver, read from its
    own log the way supervisor.sh decides it: 60 s, or 60 s per consecutive
    immediate failure (an exit under 30 s) up to four, plus a minute of
    slack; after five it has stood down, and there is no grace."""
    if log_lines and "standing down" in log_lines[-1]:
        return 0.0
    fast = 0
    for line in reversed(log_lines):
        if "supervisor started" in line:
            break          # a new supervisor starts its count at zero
        if "driver exited" not in line:
            continue
        quick = "after " in line and int(line.rsplit("after ", 1)[1].rstrip("s") or 0) < 30
        aware = supervisor_restart_aware(log_lines) if restart_aware is None else restart_aware
        # Only a restart-aware supervisor that predates B6 spares a quick rc 75;
        # one that counts quick exits backs off on it like any quick death.
        spared = aware and not supervisor_counts_quick_exits(log_lines)
        if quick and not (spared and "rc=75 " in line + " "):
            fast += 1
            continue
        break
    return 60.0 * max(1, min(fast, 4)) + SLACK_SECONDS


def supervisor_restart_aware(log_lines: list[str]) -> bool:
    """Whether the supervisor now running was started on the restart brick —
    its start line says so; an older one counts rc 75 as a crash."""
    for line in reversed(log_lines):
        if "supervisor started" in line:
            return "restart-aware" in line
    return False


def supervisor_counts_quick_exits(log_lines: list[str]) -> bool:
    """Whether the supervisor now running counts a quick rc 75 toward its
    failure count (B6) — its start line says so; the one before it spared rc 75
    and restarted a driver that died in 0 seconds once a minute, for ever."""
    for line in reversed(log_lines):
        if "supervisor started" in line:
            return "quick exits counted" in line
    return False
