"""A builder call that does nothing for ten minutes is stopped and tried once more (issue #251).

`claude -p` prints its JSON only at the end, so a call that stalled (epoll_wait, 12 seconds of CPU in 44
minutes, no child process) looked exactly like one that was thinking, and held the run until the two-hour
timeout. The runner now stops a call whose process group is only the call itself and has used almost no
CPU for the idle window; anything running under it, or any real CPU, starts a new window.
"""

import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import provider_call
import providers
import runner
import runner_idle
import tmp_root  # noqa: F401

EXPECTED_TESTS = 6
BUSY = "import time\nstart = time.time()\nwhile time.time() - start < 3:\n    pass\n"


class Idle(unittest.TestCase):
    def setUp(self):
        patched = mock.patch.object(runner_idle, "IDLE_POLL", 0.2)
        patched.start()
        self.addCleanup(patched.stop)

    def test_a_sleeping_call_is_stopped_after_the_window(self):
        started = time.monotonic()
        with self.assertRaises(runner.Idle):
            runner.run(["sleep", "30"], timeout=60, idle=1)
        self.assertLess(time.monotonic() - started, 10)

    def test_an_idle_stop_is_still_a_timeout_to_every_old_handler(self):
        self.assertTrue(issubclass(runner.Idle, subprocess.TimeoutExpired))

    def test_a_call_using_cpu_is_left_alone(self):
        done = runner.run(["python3", "-c", BUSY], timeout=60, idle=1)
        self.assertEqual(0, done.returncode)

    def test_a_call_with_a_child_running_is_left_alone(self):
        done = runner.run(["sh", "-c", "sleep 2; sleep 2; echo done"], timeout=60, idle=1)
        self.assertEqual("done\n", done.stdout)


class Retry(unittest.TestCase):
    def test_a_stalled_call_is_tried_once_more(self):
        done = subprocess.CompletedProcess([], 0, "built", "")
        stall = runner.Idle(["claude"], 600)
        with mock.patch.object(runner, "run", side_effect=[stall, done]) as run:
            self.assertIs(done, provider_call._run(["claude"], "prompt", idle=600))
        self.assertEqual(2, run.call_count)

    def test_a_second_stall_ends_the_call_as_a_crash_that_says_so(self):
        stall = runner.Idle(["claude"], 600)
        with mock.patch.object(runner, "run", side_effect=[stall, stall]) as run:
            out = providers.claude("unused", "prompt", account="work", cwd=tempfile.mkdtemp())
        self.assertEqual(("crash", 2), (out.kind, run.call_count))
        self.assertIn("stalled twice", out.text)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())   # the six above and this one


if __name__ == "__main__":
    unittest.main()
