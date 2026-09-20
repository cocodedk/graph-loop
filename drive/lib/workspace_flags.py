"""The two flags a person leaves for the driver, read between tasks.

`stop.flag` ends the campaign (the supervisor stands down too). `restart.flag`
ends this driver only: consumed once, so the driver the supervisor starts next
does not stop again — killing a driver mid-turn dropped a gate-green build;
this never can. The idle wait looks at both so a flag is not left waiting out
a 300-second sleep.
"""

from __future__ import annotations

import hashlib
import pathlib
import time

from workspace_claims import _now

STOP = "stop.flag"
RESTART = "restart.flag"
RESTART_EXIT = 75   # the driver's exit for a requested restart; supervisor.sh restarts it, counting it toward its failure backoff only when the run lasted under 30 seconds


class FlagsMixin:
    root: pathlib.Path

    def event(self, kind: str, **fields) -> dict:  # provided by Workspace
        raise NotImplementedError

    def stop(self) -> None:
        (self.root / STOP).write_text(_now(), "utf-8")
        self.event("stop_requested")

    def idle(self, seconds: int, slice_seconds: int = 10) -> None:
        """Wait, but not past a stop or restart asked for meanwhile; the
        restart flag is only looked at here, never consumed."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if (self.root / STOP).exists() or (self.root / RESTART).exists():
                return
            time.sleep(min(slice_seconds, max(0.0, deadline - time.monotonic())))

    def stop_or_restart(self) -> str:
        """"stop", "restart" or "": both flags read (the restart flag consumed
        even when the stop wins, or a later resume would exit on it)."""
        restart = self.restarting()
        if self.stopping():
            return "stop"
        return "restart" if restart else ""

    def code_digest(self) -> str:
        """What the loop's own code IS, not when it was last written to.

        This read mtimes, and a `git checkout` rewrites the mtime of every file
        the commit touches whether or not its bytes changed — so a campaign run
        while the loop is being fixed stands its driver down between tasks for
        code that is byte for byte what it was already running, and waits for a
        supervisor that a person running `drive-goal.py run` by hand is not
        running (2026-09-18). Hashing what is loaded answers the question that
        was always meant: is the code on disk the code this driver started on?
        """
        here = pathlib.Path(__file__).parent
        loaded = [path for path in here.glob("*.py") if not path.name.startswith("view")]
        loaded += [here.parent / "drive-goal.py", here.parent / "drive_commands.py"]
        stamp = hashlib.sha256()
        for path in sorted(loaded):
            if path.exists():
                stamp.update(path.name.encode())
                stamp.update(path.read_bytes())
        return stamp.hexdigest()

    def code_changed(self, since: str) -> bool:
        """Whether the loop's code on disk differs from what this driver
        started on. It restarts itself between tasks then, so the supervisor
        starts one on the new code."""
        return bool(since) and self.code_digest() != since

    def restarting(self) -> bool:
        """A restart asked for between tasks: the flag is consumed so the
        driver the supervisor starts next does not stop again. Killing the
        driver mid-turn dropped a gate-green build; this never can."""
        flag = self.root / RESTART
        if not flag.exists():
            return False
        flag.unlink()
        self.event("restart_requested")
        return True

    def stopping(self) -> bool:
        return (self.root / STOP).exists()
