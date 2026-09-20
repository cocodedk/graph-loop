"""What a builder may never run, regardless of task: `git push` from inside a
private clone reaches the repo's own receive-pack, past the checkout's own
hook (`test_worktree_private_refs.py::test_a_push_by_the_repos_own_path_is_stopped_by_the_tool_fence_not_the_hook`
shows what a raw push does beneath this fence). `builder_denies` is the loop's own fence
against it — the rig lives in `test_loop`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from test_loop import Fakes, loop_for, task
from tools import builder_denies

EXPECTED_TESTS = 3


class PushDenyTest(unittest.TestCase):
    def test_a_code_builder_is_handed_the_push_deny(self):
        self.assertIn("Bash(git push *)", builder_denies(task()))
        fakes = Fakes()
        loop, book, _ = loop_for(task(), fakes)
        loop.run_task(book.task("T1"))
        self.assertIn("Bash(git push *)", fakes.denies[-1])   # what the provider call actually got

    def test_a_live_builder_is_handed_the_push_deny_too(self):
        row = task(gate_has_side_effects=True, gate="true", helper_verbs=["journal"])
        self.assertIn("Bash(git push *)", builder_denies(row))
        fakes = Fakes()
        loop, book, _ = loop_for(row, fakes)
        loop.run_task(book.task("T1"))
        self.assertIn("Bash(git push *)", fakes.denies[-1])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
