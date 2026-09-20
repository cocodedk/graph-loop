"""Is the loop alive: the driver's start time, the supervisor's last word, and
the red flag for a driver that should be running and is not."""

from __future__ import annotations

import pathlib
import subprocess
import time

import where
from view_base import (  # noqa: F401 — the door stays here
    base_behind,
    base_measure,
    has_kept_commit,
    recorded_branch,
)
from view_supervisor_policy import (  # noqa: F401 — the door stays here
    SLACK_SECONDS,
    restart_grace,
    supervisor_counts_quick_exits,
    supervisor_restart_aware,
)
from workspace_claims import _started

CAMPAIGN = where.campaign()


def _ps_rows() -> list[list[str]]:
    out = subprocess.run(["ps", "-eo", "pid,etimes,args"], capture_output=True, text=True,
                         check=False).stdout
    return [line.split() for line in out.splitlines()[1:]]


def _driver_row(rows: list[list[str]], events: list[dict]) -> list[str] | None:
    """THIS campaign's running driver's ps row: the pid its last
    `driver_started` event announced, when that process is alive and is a
    driver by the identity rule — never the host's first driver, which may be
    another campaign's. A campaign with NO announcement at all is still on a
    pre-brick driver: the host's driver is the best reading, and the board's
    rollout advice is exactly for it."""
    announced = [row for row in events if row.get("kind") == "driver_started"]
    last = announced[-1] if announced else None
    for parts in rows:
        if not parts or is_loop_process(parts) != "driver":
            continue
        if last is None:
            return parts
        if parts[0] != str(last.get("pid")):
            continue
        # the pid alone can be reused: the announced identity (boot id and start
        # tick, as a claim records it) must be the live process's
        if last.get("started") and _started(int(parts[0])) != last["started"]:
            return None
        return parts
    return None


def _driver_start(rows: list[list[str]] | None, events: list[dict]) -> float | None:
    """When this campaign's driver started, as an epoch; None when it is not
    running. `rows` are `ps -eo pid,etimes,args` lines split into words
    (read here when None, so a test can hand in its own)."""
    parts = _driver_row(_ps_rows() if rows is None else rows, events)
    return time.time() - int(parts[1]) if parts else None


SUPERVISOR_SCRIPTS = ("supervisor.sh",)


def is_loop_process(parts: list[str]) -> str:
    """"driver" for `python… drive-goal.py run`, "supervisor" for
    `bash …/supervisor.sh` (or the old name), "" for anything else — the
    supervisor's own `drive-goal.py report` snapshot, an editor on the script,
    a grep — read from the binary and its script, never from a substring."""
    if len(parts) < 4:
        return ""
    binary, script = pathlib.Path(parts[2]).name, pathlib.Path(parts[3]).name
    if binary == "bash" and script in SUPERVISOR_SCRIPTS:
        return "supervisor"
    if binary.startswith("python") and script == "drive-goal.py" and parts[4:5] == ["run"]:
        return "driver"
    return ""


def supervisor_running(rows: list[list[str]] | None = None, campaign=None) -> bool:
    """Whether THIS campaign's own supervisor is alive: the pid it wrote when
    it took its lock, still a supervisor by the identity rule. Any
    `supervisor.sh` on the host used to answer, so campaign B's live pair hid
    campaign A's dead one and A's board stayed green (astra round 4, finding
    15). No pid recorded is no supervisor: a pre-brick one is restarted, and
    saying nothing runs is the safe reading of "we cannot tell".

    # ponytail: a recycled pid running ANOTHER campaign's supervisor reads as
    # ours. Upgrade path: record the start tick beside the pid, the way a
    # driver's claim does (`workspace_claims._started`).
    """
    try:
        pid = ((CAMPAIGN if campaign is None else campaign) / "supervisor.pid").read_text("utf-8")
    except OSError:
        return False
    pid = pid.strip()
    return bool(pid) and any(parts[:1] == [pid] and is_loop_process(parts) == "supervisor"
                             for parts in (_ps_rows() if rows is None else rows))


def driver_missing(supervisor: bool, driver: bool, log_tail,
                   exited_seconds_ago: float) -> str:
    """The red flag for a driver that is not running: this campaign's
    supervisor is up, its own driver is not, and the supervisor's last word was
    an exit longer ago than its own restart pause (`restart_grace`). Empty when
    all is well, or when the supervisor is simply between exit and restart.

    Both facts are handed in — `supervisor_running` and the announced driver
    pid — because reading them off a list of the host's processes let another
    campaign's pair answer for this one's (astra round 4, finding 15)."""
    lines = list(log_tail) if isinstance(log_tail, list) else [str(log_tail)]
    if not supervisor or driver:
        return ""
    last = lines[-1] if lines else ""
    if "driver exited" in last and exited_seconds_ago <= restart_grace(lines):
        return ""
    return ("  !! no driver is running — the supervisor should have restarted it; "
            "read its log (supervisor.log) and start `bash supervisor.sh` if it stood down")


def _supervisor_last_word() -> tuple[list[str], float]:
    """The supervisor log's last lines and how many seconds ago it last wrote."""
    for name in ("supervisor.log",):
        path = CAMPAIGN / name
        if path.exists():
            lines = path.read_text("utf-8").strip().splitlines()
            return lines[-400:], time.time() - path.stat().st_mtime   # back past any run of exits to the start marker
    return [], 0.0




def stale_driver_line(age_minutes: int, knows_flag: bool, flag: str, supervised: bool = True) -> str:
    """The driver runs older code than the checkout. A driver that started on
    the flag brick restarts by the flag; one that predates it is switched by
    the stop flag, which every driver reads between tasks. Without a
    supervisor the same stop-flag switch applies — a supervisor started
    beside a live driver would be a second driver."""
    stop = str(pathlib.Path(flag).with_name("stop.flag"))
    if not supervised:
        return (f"  !! the driver ({age_minutes}m old) is OLDER than the loop's code and NO restart-aware supervisor owns it — "
                f"`touch {stop}`: the driver exits between tasks; then remove the stop flag and start "
                "`bash drive/supervisor.sh` (started beside a live driver it would be a second driver)")
    if knows_flag:
        return (f"  !! the driver ({age_minutes}m old) is OLDER than the loop's code — `touch {flag}`: "
                "it restarts between tasks, never mid-turn (a kill once dropped a gate-green build)")
    return (f"  !! the driver ({age_minutes}m old) is OLDER than the loop's code and predates restart.flag — "
            f"`touch {stop}`: it stops between tasks and the supervisor stands down; then remove the "
            "stop flag and start `bash drive/supervisor.sh`. Never kill it: an empty "
            "claims.json is a snapshot, and a supervisor started beside a live driver is a second driver")


def driver_knows_flag(rows: list[dict], pid: int | None) -> bool:
    """Whether the running driver announced itself — only a driver on the
    flag brick writes `driver_started` with its pid."""
    return pid is not None and any(row.get("kind") == "driver_started" and row.get("pid") == pid for row in rows)


def _driver_pid(rows: list[list[str]] | None = None, events: list[dict] | None = None) -> int | None:
    """This campaign's running driver's pid (see `_driver_row`); None when
    the announced driver is gone or none was announced."""
    parts = _driver_row(_ps_rows() if rows is None else rows, events or [])
    return int(parts[0]) if parts else None


def supervisor_owns_driver(pid: int | None, rows: list[list[str]] | None = None) -> bool:
    """Whether THIS driver (by pid) is a child of a running supervisor — read
    from `ps -eo pid,ppid,etimes,args`: a supervisor that merely exists (an
    old one, or another campaign's pair) restarts nothing of ours."""
    if pid is None:
        return False
    if rows is None:
        out = subprocess.run(["ps", "-eo", "pid,ppid,etimes,args"], capture_output=True, text=True,
                             check=False).stdout
        rows = [line.split() for line in out.splitlines()[1:]]
    supervisors = {parts[0] for parts in rows
                   if len(parts) > 2 and is_loop_process([parts[0]] + parts[2:]) == "supervisor"}
    return any(len(parts) > 2 and parts[0] == str(pid) and parts[1] in supervisors
               and is_loop_process([parts[0]] + parts[2:]) == "driver"     # the child must BE the driver
               for parts in rows)


def driver_is_working(pid: int | None, rows: list[list[str]] | None = None) -> bool:
    """Whether the driver has a child running: a gate writes no events, and reading
    only for a model call reported every long gate as a stalled driver."""
    if pid is None:
        return False
    if rows is None:
        out = subprocess.run(["ps", "-eo", "pid,ppid"], capture_output=True, text=True, check=False)
        rows = [line.split() for line in out.stdout.splitlines()[1:]]
    return any(len(parts) > 1 and parts[1] == str(pid) for parts in rows)
