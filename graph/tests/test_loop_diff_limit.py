"""Loop-level: a diff over DIFF_LIMIT ends its round exactly the way any
rejected diff does — back to the builder with the finding, to the round cap
— never a shortcut around the ordinary rebuild path. The prompt-level refusal
is `test_prompts_diff_limit`; the rig (`Fakes`, `loop_for`, `task`) lives in
`test_loop`, read-only here.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from prompts import DIFF_LIMIT
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 1


class DiffLimitLoopTest(unittest.TestCase):
    def test_an_oversized_diff_is_sent_back_like_any_rejected_diff(self):
        # "two" so the gate (grep -q two a.py) passes; padded well past the
        # limit so the diff itself, not just the file, is over it.
        fakes = Fakes(edit="two" + "x" * (DIFF_LIMIT + 10_000) + "\n")
        loop, book, space = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", out.state)
        self.assertIn("reduce it or split the card", out.why)
        # the contract review ran (round one, always); the diff was too large
        # to show a reviewer at all, so the diff review never happened
        self.assertEqual(["review", "build:work"], fakes.calls)
        queued = book.task("T1")
        self.assertEqual("todo", queued["status"])          # offered again, same as any REJECT
        self.assertEqual(1, queued["rebuild_round"])
        self.assertEqual(out.worktree, queued["rebuild_from"])
        self.assertIn("reduce it or split the card", queued["rejections"][-1])
        self.assertEqual("rebuild_queued",
                         [r for r in space.events() if r.get("task") == "T1"][-1]["kind"])
        self.assertTrue(pathlib.Path(out.worktree).is_dir())  # the tree stays, kept

        # the same card, its builder now keeping the diff small: reviewed
        # normally, in the same worktree, no second contract review.
        fakes.edit = "two\n"
        calls_before = list(fakes.calls)
        again = loop.run_task(book.task("T1"))
        self.assertEqual("done", again.state)
        self.assertEqual(out.worktree, again.worktree)       # same worktree
        self.assertEqual(["build:work", "review"], fakes.calls[len(calls_before):])
        self.assertEqual("done", book.task("T1")["status"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
