"""A gate that edits the tree it judges is charged to the card that owns it.

Red first (astra round 3, finding 15): the mutation fault was a plain
`RuntimeError`, and `loop_judge._keep` catches only `CombinedGateFailed` — so an
older card's defective gate escaped the whole judge, the mutating card stayed
`done` with nobody assigned to repair it, and the innocent builder lost its lane.
The fault is a `CombinedGateFailed` now, carrying the gate it names, and takes
the same repair route as a gate that is red on the branch tip. The rig lives in
`test_loop`; the sibling routing cases live in `test_keep_combined_owner`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from loop import Loop
from test_loop import Fakes, repo_with, task

EXPECTED_TESTS = 1

# Kept before this card, and its gate rewrites a file instead of reading one:
# whatever it then says, it judged its own edit and not the commit.
# The grant names the affected file, so scoped selection reaches attribution.
MUTATES = {"id": "T9", "goal": "a.py is looked at", "status": "done", "needs": [],
           "files": ["a.py"], "gate": "echo mutated > a.py",
           "done_when": "a.py was looked at", "kept_at": "2026-08-30T10:00:00Z"}


class MutatingGateTest(unittest.TestCase):
    def test_a_gate_that_edits_the_tree_is_routed_to_its_owner_uncharged(self):
        fakes = Fakes()
        root, book, space = repo_with(task(), [MUTATES])
        loop = Loop(repo=root, backlog=book, space=space, build=fakes.builder,
                    review=fakes.reviewer, branch="campaign/test")
        loop.run_task(book.task("T1"))
        # T9 is already done: reopening finished work for a defect this card's
        # builder cannot answer would only spend rounds retrying into the same
        # mutating gate, so the owner is left exactly as it was.
        self.assertEqual(MUTATES, book.task("T9"))
        mine = book.task("T1")
        self.assertEqual(0, int(mine.get("rebuild_round") or 0))   # not this card's round
        self.assertTrue(mine["blocked_by_human"])              # parked for a person to decide
        self.assertIn("edited the tree it judged", mine["refused_why"])
        clash = [event for event in space.events() if event.get("kind") == "failed"
                 and event.get("step") == "combined_gate"]
        self.assertEqual(["T9"], [event["gate_owner"] for event in clash])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
