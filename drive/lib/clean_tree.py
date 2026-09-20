"""A clean detached checkout of one commit, and its removal.

Two callers cut the same checkout for the same reason: what a model is shown
must be the work this campaign kept, not the working tree somebody is editing.
The slicer plans against it (`slice_turn`) — one function, because a second
copy of it would drift.

The checkout and the temp parent that held it both go when the block ends,
however it ends: one empty parent per planning call stayed behind, and /tmp
filling on 2026-09-03 killed every process on the host.
"""

from __future__ import annotations

import contextlib
import pathlib
import shutil
import subprocess
import tempfile
from collections.abc import Iterator

import where

# The name the slicer's own leak test knows (`test_turn_slice_tmp`); every
# checkout this cuts is one planning or deciding call's, whoever asked.
PREFIX = "slice-repo-"


@contextlib.contextmanager
def checkout(tip: str) -> Iterator[tuple[pathlib.Path | None, str]]:
    """The checkout of `tip`, or None and why there is none.

    Fail CLOSED is the caller's job and every caller does it: reading an
    unrelated HEAD is planning against the wrong code, and deciding against it
    is a drop written about work that is there.

    A checkout that could not be SET UP answers the same way git refusing to
    make one does. Cutting one starts by making a temporary directory, which is
    the first thing a full disk fails, and that error escaping the block left
    the caller's slot spent with no provider ever asked (an independent review,
    finding 4). The cleanup answers the same way — starting git can fail there
    too, and that error escaping skipped the removal of the parent and spent the
    grant as well (an independent review, finding 2). Only this module's own calls
    are caught: an error the BODY raises is the caller's own and travels on,
    past a cleanup that always runs.
    """
    parent = None
    try:
        parent = pathlib.Path(tempfile.mkdtemp(prefix=PREFIX))
        made = subprocess.run(["git", "-C", str(where.repo()), "worktree", "add",
                               "--detach", "-f", str(parent / "tree"), tip],
                              capture_output=True, text=True, check=False)
        cut = (None, made.stderr.strip()[:200]) if made.returncode else (parent / "tree", "")
    except OSError as fault:
        cut = (None, str(fault)[:200])
    try:
        yield cut
    finally:
        if parent is not None:
            try:
                subprocess.run(["git", "-C", str(where.repo()), "worktree", "remove",
                                "--force", str(parent / "tree")],
                               capture_output=True, check=False)
            except OSError:
                # git could not be STARTED (no fork, no binary). Raising here
                # would leave the caller's grant spent and the directory on the
                # disk it is already short of: the files go below either way,
                # and `git worktree prune` clears the admin entry left behind
                # (an independent review, finding 2).
                pass
            finally:
                shutil.rmtree(parent, ignore_errors=True)
