"""The planner dies with the slicer, which dies with the driver.

Codex, round 3: binding the driver's children was not enough. The slicer is a
child of the driver and dies with it, but it started its own planner with
`subprocess.run`, so a SIGKILLed driver left a planner running and spending —
the three-level chain holds only when every level starts its child the same
way.
"""

from __future__ import annotations

import os
import pathlib
import signal
import subprocess
import sys
import time
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
GRAPH_LIB = HERE.parents[0] / "graph" / "lib"
EXPECTED_TESTS = 2

# The middle level: a real `intelligence.ask` whose planner command is a sleep
# that writes its own pid. Only the belt and the command are stood in for; the
# call itself is the one the slicer makes.
SLICER = """
import pathlib, sys, types, unittest.mock
sys.path.insert(0, {here!r})
import intelligence
belt = [types.SimpleNamespace(model="m", account="work", agent="claude")]
with (unittest.mock.patch.object(intelligence.resources, "belt", return_value=belt),
      unittest.mock.patch.object(intelligence.accounts, "environment", return_value=({{}}, ())),
      unittest.mock.patch.object(intelligence, "_argv",
                                 return_value=["bash", "-c",
                                               "echo $$ > {planner}; exec sleep 300"])):
    intelligence.ask("plan this", pathlib.Path("."))
"""

# The top level: the driver, starting the slicer the way the graph loop does.
DRIVER = """
import sys
sys.path.insert(0, {lib!r})
from runner import run
run([{python!r}, {slicer!r}], timeout=300)
"""


def gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def kill(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


class ThreeLevelDeathTest(unittest.TestCase):
    def test_a_planner_does_not_outlive_the_driver_that_was_paying_for_it(self):
        import tempfile
        tmp = pathlib.Path(tempfile.mkdtemp())
        planner_pid, slicer, driver_py = tmp / "planner", tmp / "slicer.py", tmp / "driver.py"
        slicer.write_text(SLICER.format(here=str(HERE), planner=planner_pid))
        driver_py.write_text(DRIVER.format(lib=str(GRAPH_LIB), python=sys.executable,
                                           slicer=str(slicer)))
        driver = subprocess.Popen([sys.executable, str(driver_py)])
        self.addCleanup(driver.wait)
        self.addCleanup(driver.kill)
        deadline = time.monotonic() + 60
        while not (planner_pid.exists() and planner_pid.read_text().strip()):
            self.assertLess(time.monotonic(), deadline, "the planner never started")
            time.sleep(0.05)
        planner = int(planner_pid.read_text())
        self.addCleanup(kill, planner)

        os.kill(driver.pid, signal.SIGKILL)
        driver.wait(timeout=10)
        end = time.monotonic() + 10
        while not gone(planner) and time.monotonic() < end:
            time.sleep(0.05)
        self.assertTrue(gone(planner),
                        "the planner outlived the driver that was paying for it")


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS, found)


if __name__ == "__main__":
    unittest.main()
