"""Is the loop alive, and what is standing in its way.

Split from `view` at the 200-line cap. `health` is what the screen shows;
`health_failures` is the part `--check` must go red on, and both read the same
function so the cheap look cannot miss what the screen says.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile

import gate_sandbox
import notice
import where
from view_health import is_loop_process, supervisor_running
from view_stamps import stamped

CAMPAIGN = where.campaign()


def health() -> list[str]:
    out = subprocess.run(["ps", "-eo", "pid,etime,args"], capture_output=True,
                         text=True, check=False).stdout
    rows = [line.split() for line in out.splitlines()]
    ours = [(is_loop_process(parts), parts) for parts in rows]
    lines = [f"  {parts[0]} {parts[1]} {' '.join(parts[2:5])}" for kind, parts in ours if kind]
    if not gate_sandbox.works():
        # A standing fact about this host, not a fault of the run: said where a
        # reader sees it, never as a red flag, because a flag that is always up
        # is a flag nobody reads.
        lines.append("  gates run unconfined on this host (bubblewrap cannot map uids); "
                     "their environment is still scrubbed of credentials")
    return lines + health_failures(ours)


def health_failures(ours: list | None = None) -> list[str]:
    """The states no board can show as normal. `red_flags` reads the same
    function the screen does: `--check` said "no red flags" while nothing was
    left to restart the driver, and that is the one thing it exists to catch.

    A stand-down nobody was told about is one of them: supervisor.sh leaves its
    last words in `stand-down.txt` and only a proven delivery removes the file
    (alert-watcher.sh), so until then every check carries it — to the messenger
    each tick, and to the owner's mail once it has stood 15 minutes."""
    if ours is None:
        out = subprocess.run(["ps", "-eo", "pid,etime,args"], capture_output=True,
                             text=True, check=False).stdout
        ours = [(is_loop_process(parts), parts)
                for parts in (line.split() for line in out.splitlines())]
    lines = []
    # THIS campaign's supervisor, by the pid it recorded — a supervisor with a
    # matching name is another campaign's as often as ours (view_health)
    if not supervisor_running([parts for _, parts in ours], CAMPAIGN):
        lines.append("  SUPERVISOR IS NOT RUNNING — nothing will restart the driver")
    if (CAMPAIGN / "stop.flag").exists():
        lines.append("  STOP FLAG IS SET — the driver will stand down")
    fatal = (CAMPAIGN / "stand-down.txt")
    if fatal.exists():
        # its own words, minus the time it wrote itself (notice.body): `stamped`
        # gives every flag one age, and two ages on one line contradict
        said = notice.body(fatal.read_text("utf-8"))
        if said:
            lines.append(said)
    if disk_pressure():
        # the full disk of 2026-09-03 killed every process on the host,
        # authentication included, with no warning before it: this line is the
        # warning, and the supervisor stands down on the same reading
        lines.append(disk_line())
    return stamped(lines, "health", CAMPAIGN)


DISK_FLOOR_GB = 20.0


def disk_free_gb(path: str) -> float:
    try:
        return shutil.disk_usage(path).free / 1e9
    except OSError:
        return float("inf")           # an unreadable filesystem is not a full one


def disk_pressure() -> bool:
    """Whether the disk the worktrees live on is low enough to stop the loop.

    The ONE reading of it: the board's red line above and supervisor.sh's
    stand-down both ask this, so what a person is told and what the loop does
    can never disagree — a warning that mailed the owner while the loop kept
    running was a human route of its own (astra round 4, finding 16)."""
    return disk_free_gb(tempfile.gettempdir()) < DISK_FLOOR_GB


def disk_line() -> str:
    """The words for a disk about to fill, written once here: the board shows
    them and the supervisor's stand-down notice quotes them (it asks for them
    below rather than writing its own, which would drift from these)."""
    return (f"  {notice.DISK} — {disk_free_gb(tempfile.gettempdir()):.1f} GB free where the "
            f"worktrees live (floor {DISK_FLOOR_GB} GB); the sweep runs every tick, remove "
            "what it may not")


if __name__ == "__main__":      # supervisor.sh asks before it starts a driver
    if not disk_pressure():
        raise SystemExit(1)
    print(disk_line().strip())
    raise SystemExit(0)
