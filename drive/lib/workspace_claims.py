"""Who is working on what right now.

The claims file is the truth about "now": a claim names the task, the process
that holds it, its process group and its worktree, and clears itself when the
claimant's process dies. Liveness is the claimant's own pid: the driver shares
its process group with the supervisor that restarts it, so a group that is
still there says nothing about a driver that was killed. The event log keeps
history; this file keeps the present.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import signal

import workspace_kill

CLAIMS = "claims.json"


def _boot() -> str | None:
    try:
        return pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return None     # a machine without the file says nothing about any process


def _started(pid: int) -> str | None:
    """The process's identity beyond its pid: this boot's id and the process's
    start tick from /proc. A pid can be reused, and after a reboot the tick
    counter starts over; the triple (boot, pid, tick) cannot repeat.

    "" means no such process. None means the identity could not be read —
    doubt, which never abandons a claim."""
    boot = _boot()
    if boot is None:
        return None
    try:
        tick = pathlib.Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()[19]
    except (FileNotFoundError, ProcessLookupError):
        return ""
    except OSError:
        return None
    return f"{boot}:{tick}"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _alive(row: dict) -> bool:
    """Whether the process that made this claim is still there.

    The claimant's pid decides when the claim carries one; the group alone is
    the old shape. A driver that was killed leaves its claim behind, and a
    later run that believed it would refuse to start the task for ever.
    """
    try:
        if int(row.get("pid") or 0):
            start, recorded = _started(int(row["pid"])), row.get("started")
            if not recorded:               # claimed in doubt: the pid alone decides
                os.kill(int(row["pid"]), 0)
            elif start is not None and (not start or start != recorded):
                return False               # gone, or the pid reused since
        else:
            os.killpg(int(row["pgid"]), 0)
    except (ProcessLookupError, ValueError, KeyError):
        return False
    except PermissionError:
        return True                        # someone else's group: still a process
    return True


def _verified(pid: int, recorded: str | None) -> bool:
    """True only when `recorded` is non-empty and matches `_started(pid)`
    exactly — never signal on doubt, an empty recording, or a changed identity."""
    return bool(recorded) and _started(pid) == recorded


class ClaimsMixin:
    """Mixed into Workspace: everything here reads `self.root` and writes
    events through `self.event`."""

    root: pathlib.Path

    def event(self, kind: str, **fields) -> dict:  # provided by Workspace
        raise NotImplementedError

    def only_writer(self):                        # provided by Workspace
        raise NotImplementedError

    # ----------------------------------------------------------------- claims

    def _claims(self) -> dict:
        path = self.root / CLAIMS
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text("utf-8"))
        except ValueError:
            return {}

    def _write_claims(self, claims: dict) -> None:
        # Written beside and renamed: a reader never sees half a file, whatever
        # the lock does — rename is atomic on the same filesystem.
        beside = self.root / (CLAIMS + ".new")
        beside.write_text(json.dumps(claims, indent=2, sort_keys=True), "utf-8")
        beside.replace(self.root / CLAIMS)

    def claim(self, task_id: str, *, pgid: int, account: str, worktree: str,
              pid: int = 0, again: bool = False) -> None:
        with self.only_writer():
            claims = self._claims()
            claims[task_id] = {"pid": pid, "started": _started(pid) if pid else "", "pgid": pgid,
                           "account": account, "worktree": worktree,
                               "since": _now()}
            self._write_claims(claims)
        if not again:   # the loop re-claims only to record the worktree: one claim, one line
            self.event("claimed", task=task_id, account=account, pgid=pgid,
                       worktree=worktree)

    def release(self, task_id: str) -> None:
        with self.only_writer():
            claims = self._claims()
            gone = claims.pop(task_id, None) is not None
            if gone:
                self._write_claims(claims)
        if gone:
            self.event("released", task=task_id)

    def claimed_now(self) -> dict:
        """The claims that are alive, without taking the lock and without pruning.

        `running` is a writer: it locks twice and drops the dead rows. The board
        called it and waited behind a keep. This answers the same question for a
        reader — the same liveness test, so a dead claim never reads as a busy
        lane and hides a starved queue."""
        return {task_id: row for task_id, row in self._claims().items() if _alive(row)}

    def running(self) -> dict:
        """The tasks still in flight — a claim whose process is gone is not.

        A driver that was killed leaves its claim behind, and a later run that
        believed it would refuse to start the task for ever. The claimant's pid
        decides when the claim carries one; the group alone is the old shape."""
        alive, abandoned = {}, []
        with self.only_writer():          # one snapshot, and never a half-written file
            rows = self._claims()
        for task_id, row in rows.items():
            if _alive(row):
                alive[task_id] = row
            else:
                abandoned.append((task_id, row))
        if abandoned:
            with self.only_writer():
                # Re-read under the lock and drop only the exact rows that were dead:
                # a lane may have claimed the same task since, and that claim is live.
                claims = self._claims()
                for task_id, row in abandoned:
                    if claims.get(task_id) == row:
                        claims.pop(task_id, None)
                self._write_claims(claims)
            self.event("abandoned", tasks=[task_id for task_id, _ in abandoned])
        return alive

    def kill_running(self, signal_number: int = 15) -> list[str]:
        """Freeze each claimed process (SIGSTOP), let `workspace_kill.
        finish_kill` signal its children then itself, then release the
        freeze; worktrees stay. Claims sharing one (pid, pgid, started) —
        parallel lanes on the same driver — are grouped and verified once:
        a stale row's `started` never decides a valid row's verdict merely
        because they share a pid and pgid, or the reverse."""
        groups: dict[tuple[int, int, str | None], list[str]] = {}
        for task_id, row in self._claims().items():
            try:
                key = (int(row.get("pid") or 0), int(row["pgid"]), row.get("started"))
            except (KeyError, ValueError):
                continue
            groups.setdefault(key, []).append(task_id)
        stopped, unverified, unresolved = [], [], []
        for (pid, pgid, recorded), task_ids in groups.items():
            if not _verified(pid, recorded):
                unverified.extend(task_ids)
                continue
            try:
                os.killpg(pgid, signal.SIGSTOP)
            except (ProcessLookupError, PermissionError):
                continue
            gone = workspace_kill.finish_kill(pgid, pid, signal_number)
            stopped.extend(task_ids) if gone else unresolved.extend(task_ids)
        if stopped:
            self.event("killed", tasks=stopped, signal=signal_number)
        if unverified:
            self.event("unverified", tasks=unverified)
        if unresolved:
            self.event("unresolved", tasks=unresolved)
        return stopped
