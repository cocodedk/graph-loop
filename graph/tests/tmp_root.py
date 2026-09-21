"""Everything a test process puts in /tmp lives under one root that goes at
exit, and the live-stack lock it reaches is this root's, never the host's.

The suite leaves ~190 worktrees per run — 7785 stood in /tmp after one day of
runs on 2026-09-08 — and the loop's own sweep must never touch what it cannot
own. Imported for its effect by the two helpers every such test uses.
"""

import atexit
import os
import pathlib
import shutil
import sys
import tempfile

# The shipped default is one account, because only the machine running the
# loop knows where a second one's configuration lives. The belt that walks to
# another account when one runs out needs two, independent of the local environment.
os.environ["GRAPH_ACCOUNTS"] = "work,second=/cfg/second"

ROOT = tempfile.mkdtemp(prefix="graph-tests-")
tempfile.tempdir = ROOT
os.environ["TMPDIR"] = ROOT          # the drivers and scripts the tests spawn follow it too
atexit.register(shutil.rmtree, ROOT, ignore_errors=True)

# The live-stack lock is one file for this whole host and NOTHING in the
# environment moves it — a knob that did was two drivers on one stack. So the
# suite stands in for the function instead. Every `Loop` built by a rig reaches
# the lock through `worktree_lock.stack_lock`, which reads this name at each
# call, so one stand-in here covers the ~15 live tests that never name the lock
# and would otherwise take the record of a driver running on this host. A test
# that wants its own folder patches this same name and gets it back after.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import worktree_lock

worktree_lock.shared = lambda: str(pathlib.Path(ROOT) / "live-lock")
