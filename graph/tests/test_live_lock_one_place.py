"""One lock file for the stack, wherever a driver's environment points, and one
writer at a time through clearing it and publishing.

Codex, on finding 6: the lock folder came from `tempfile.gettempdir()`, and
then from `GRAPH_LIVE_LOCK`, so two drivers with different environments made
two locks and both held the stack; and `take` decided the holder was gone,
then deleted and published in separate steps, so a second driver that cleared
the same dead lock first had its fresh record deleted underneath it. Both
probes admitted two holders. Nothing in the environment names the folder now,
and a test isolates itself by standing in for `worktree_lock.shared`.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import worktree_lock
from worktree import LiveLock

EXPECTED_TESTS = 3
LIB = str(pathlib.Path(__file__).resolve().parents[1] / "lib")


# A real driver, started with its own environment, that takes the lock on the
# stack named in argv and says where it looked and whether it got it. The stack
# name is the test's own throwaway, so this never reaches `graph-live`.
DRIVER = f"""
import sys
sys.path.insert(0, {LIB!r})
import worktree_lock
worktree_lock.LIVE_STACK = sys.argv[1]
lock = worktree_lock.stack_lock()
got = lock.take("T1")
print(lock.path, got)
sys.stdout.flush()
input()
lock.give_back()
"""


def a_driver(stack: str, environment: dict) -> subprocess.Popen:
    """One driver process, still holding whatever it took until it is told to
    stop: two that have both let go prove nothing about holding at once."""
    return subprocess.Popen([sys.executable, "-c", DRIVER, stack],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                            env={"PATH": "/usr/bin:/bin", **environment})


def where_and_whether(driver: subprocess.Popen) -> tuple[str, bool]:
    path, got = (driver.stdout.readline() if driver.stdout else "").rsplit(" ", 1)
    return path, got.strip() == "True"


def another_process_can_enter(folder: str) -> bool:
    """Whether a SEPARATE process can take the lock's guard right now. Separate,
    because `flock` is held per open file description: this process's own hold
    would not stop a second `open` here."""
    code = ("import fcntl, pathlib, sys\n"
            f"guard = pathlib.Path(sys.argv[1]) / {worktree_lock.GUARD!r}\n"
            "guard.parent.mkdir(parents=True, exist_ok=True)\n"
            "handle = open(guard, 'a')\n"
            "try:\n"
            "    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
            "except OSError:\n"
            "    raise SystemExit(1)\n"
            "raise SystemExit(0)\n")
    return subprocess.run([sys.executable, "-c", code, folder],
                          capture_output=True, check=False).returncode == 0


class OnePlaceTest(unittest.TestCase):
    def test_two_drivers_with_different_environments_never_both_hold_the_stack(self):
        """Whatever a driver's environment says, it meets the other driver's
        lock file. An environment that could name the folder let two of them
        each take a lock of their own and graph one stack together."""
        stack = "sc-test-" + os.urandom(4).hex()
        homes = (tempfile.mkdtemp(), tempfile.mkdtemp())
        drivers = [a_driver(stack, {"TMPDIR": home, "HOME": home,
                                    "GRAPH_LIVE_LOCK": home, "XDG_RUNTIME_DIR": home})
                   for home in homes]
        for driver in drivers:
            self.addCleanup(driver.wait)
            self.addCleanup(driver.kill)
        answers = [where_and_whether(driver) for driver in drivers]
        self.addCleanup(shutil.rmtree, pathlib.Path(answers[0][0]).parent, True)

        self.assertEqual(answers[0][0], answers[1][0], "two drivers, two lock files")
        self.assertEqual(1, sum(got for _, got in answers),
                         "both drivers held the same stack at once")


class GuardedSequenceTest(unittest.TestCase):
    def test_no_other_driver_can_clear_and_publish_inside_the_same_sequence(self):
        """The stale check, the delete and the publish are one hold. Without it
        two drivers both read one dead holder, both delete it, and both
        publish — the second record replacing the first, unnoticed."""
        folder = tempfile.mkdtemp()
        (pathlib.Path(folder) / worktree_lock.LOCK).write_text("T0 999999 boot:1")
        lock = LiveLock(folder)
        seen: list[bool] = []
        real_link = os.link

        def look_before_publishing(src, dst):
            seen.append(another_process_can_enter(folder))
            return real_link(src, dst)

        with unittest.mock.patch("worktree_lock.os.link", side_effect=look_before_publishing):
            self.assertTrue(lock.take("T1"))
        self.assertEqual([False], seen,
                         "another driver could clear and publish inside this sequence")


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
