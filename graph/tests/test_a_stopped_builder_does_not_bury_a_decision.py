"""A builder that stops and says why does not write over a newer decision.

BLOCKED and PARTIAL are the builder's own answer, and the loop wrote them
straight onto the card. The call takes an hour, and a drop, a hold or a rewrite
decided in it is newer than everything that answer was decided from:
`blocked_by_agent` over a dropped card brings the card back and asks a person
about work somebody had already settled (astra round 4, finding 2). The rig is
`test_loop`'s.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 1

STOPPED = ('{"result": "BLOCKED", "blocked": true, "needs_person": true, '
           '"why": "the fix needs a verb this agent does not have"}')


def stopping(book):
    """The builder stops and says why, with the card dropped while it ran."""

    def builder(prompt, **kwargs):
        book.set_status("T1", "dropped", refused_why="decided against")
        return Outcome("ok", text=STOPPED, cost=0.1, tokens=10)

    return builder


class StoppedBuilderCardMovedTest(unittest.TestCase):
    def test_a_card_dropped_while_the_builder_ran_stays_dropped(self):
        loop, book, space = loop_for(task(), Fakes())
        loop.build = stopping(book)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("dropped", book.task("T1")["status"])
        self.assertEqual("held", out.state)      # no later writer acts on it
        self.assertIn("card_moved", [row.get("kind") for row in space.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
