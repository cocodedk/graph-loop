"""One driver at a time in a campaign directory. Split from `workspace` at the
200-line cap; `Workspace.only_driver()` stays the front door.

Not `worktree_lock.LiveLock`, which answers a different question: that one
names its holder in a file so any process can read who has the shared live
stack. This is a flock the driver's own process holds — nothing written down,
nothing to clean up, and gone the moment the process is.
"""

from __future__ import annotations

import fcntl
import os
import pathlib

LOCK = "driver.lock"


class LockMixin:
    root: pathlib.Path

    def only_driver(self) -> None:
        """One driver per campaign, whoever started it.

        `supervisor.sh` takes `supervisor.lock` so two supervisors never double
        up, but a driver started by hand took nothing: two drivers on one
        campaign write over each other's claims. The descriptor is held open,
        never closed, exactly as the supervisor holds its own (`exec 9>`): a
        flock lasts as long as its descriptor, and the kernel closes this one
        when the driver's process ends.
        """
        held = os.open(self.root / LOCK, os.O_WRONLY | os.O_CREAT, 0o644)
        try:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(held)
            raise SystemExit(
                f"another driver already holds {self.root / LOCK} — exiting") from None
