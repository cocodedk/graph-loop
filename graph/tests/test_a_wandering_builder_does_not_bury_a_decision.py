"""A builder's scope fault does not write over a newer decision either.

The gate's version of this fault already asks the one guard
(`loop_judge_retry.gate_left_its_lane`); the builder's did not, so
`out_of_scope` landed on a card the decider had dropped while the build ran —
and `out_of_scope` is a wall the slicer then takes (astra round 4, finding 2).
The rig is `test_loop`'s.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 1


def wandering(book):
    """The builder writes outside its files, with the card dropped meanwhile."""

    def builder(prompt, *, cwd, **kwargs):
        (pathlib.Path(cwd) / "a.py").write_text("two\n")
        (pathlib.Path(cwd) / "elsewhere.py").write_text("not mine\n")
        book.set_status("T1", "dropped", refused_why="decided against")
        return Outcome("ok", text="done", cost=0.1, tokens=10)

    return builder


class WanderingBuilderCardMovedTest(unittest.TestCase):
    def test_a_card_dropped_while_the_builder_wandered_stays_dropped(self):
        loop, book, space = loop_for(task(), Fakes())
        loop.build = wandering(book)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("dropped", book.task("T1")["status"])
        self.assertEqual("held", out.state)      # `failed` is what a lane re-slices
        self.assertIn("card_moved", [row.get("kind") for row in space.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
