"""A refusal before reading keys the tree's fate on whether the tree was
reused, never on the round number: an uncharged outage leaves round 0 with a
real tree of paid work, and a later limit must not remove it (astra's review
of 2026-09-08, finding 2). A tree this call cut and nobody touched still goes,
and the card stops naming it."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from providers import Outcome
from test_loop import Fakes, loop_for, task
from worktree import Worktree

EXPECTED_TESTS = 3


def limits() -> Fakes:
    return Fakes(build=[Outcome("limit", text="usage limit reached"),
                        Outcome("limit", text="usage limit reached")], edit=None)


class RefusalKeepsReusedTreeTest(unittest.TestCase):
    def test_a_round_zero_tree_with_paid_work_survives_a_limit(self):
        fakes = limits()
        loop, book, _ = loop_for(task(), fakes)
        kept = Worktree(loop.repo, "T1", "HEAD").create()
        (pathlib.Path(kept.path) / "a.py").write_text("paid work\n")
        book.set_status("T1", "todo", rebuild_from=kept.path)      # what an uncharged outage leaves
        out = loop.run_task(book.task("T1"))
        self.assertEqual("waiting", out.state, out.why)
        self.assertEqual("paid work\n", (pathlib.Path(kept.path) / "a.py").read_text())
        self.assertEqual(kept.path, book.task("T1")["rebuild_from"])

    def test_a_tree_this_call_cut_goes_and_the_card_forgets_it(self):
        fakes = limits()
        loop, book, space = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("waiting", out.state, out.why)
        cut = [r for r in space.events() if r["kind"] == "worktree"][-1]["path"]
        self.assertFalse(pathlib.Path(cut).exists())
        self.assertFalse(book.task("T1").get("rebuild_from"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
