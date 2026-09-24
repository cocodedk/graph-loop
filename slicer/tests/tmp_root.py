"""Everything a test process puts in /tmp lives under one root that goes at
exit. The slicer suite left 101 directories in the host's /tmp per run, and
that /tmp filling on 2026-09-03 killed every process on the host. The graph
suite's guard, copied here because the two suites run as separate processes.
Imported for its effect by every module that makes temp files."""

import atexit
import os
import shutil
import tempfile

ROOT = tempfile.mkdtemp(prefix="slicer-tests-")
tempfile.tempdir = ROOT
os.environ["TMPDIR"] = ROOT          # the processes the tests spawn follow it too
atexit.register(shutil.rmtree, ROOT, ignore_errors=True)

# The card router (graph/lib/model_router.py, docs/ROUTER.md) asks a live
# decision service by default. Nothing here routes yet, but this process must
# never spend a real decision call either, the same guarantee the graph suite
# gives itself — a developer's shell exporting GRAPH_ROUTER=jev must not leak in.
os.environ["GRAPH_ROUTER"] = "off"
