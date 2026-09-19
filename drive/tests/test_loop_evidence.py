"""B4: a card with no files and no live gate has nothing to build. It takes
its own short route after the contract, through `judge`: one gate call
(credential-scrubbed; boxed when bubblewrap works) decides done or failed,
never a builder call or a diff review. The rig is `test_loop`'s."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 4


def evidence_task(**extra) -> dict:
    row = task(files=[], gate="true")
    row.update(extra)
    return row


class EvidenceGateTest(unittest.TestCase):
    def test_a_green_gate_is_done_without_a_builder_or_a_diff_review(self):
        fakes = Fakes()
        loop, book, space = loop_for(evidence_task(triage="work"), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertEqual(["review"], fakes.calls)          # the contract, and nothing else
        self.assertNotIn("triage", book.task("T1"))
        self.assertEqual("done", book.task("T1")["status"])
        self.assertIsNone(book.task("T1").get("commit"))   # no keeper commit for an evidence card
        steps = [row for row in space.events()
                if row.get("kind") == "step" and row.get("step") == "gate" and row.get("task") == "T1"]
        self.assertEqual(1, len(steps))
        artifacts = [row for row in space.events()
                    if row.get("kind") == "artifact" and row.get("name") == "gate-output"]
        self.assertEqual(1, len(artifacts))

    def test_a_red_gate_fails_without_a_builder_and_queues_a_round(self):
        fakes = Fakes()
        loop, book, _ = loop_for(evidence_task(gate="false"), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("failed", out.state)
        self.assertEqual(["review"], fakes.calls)          # the contract only, no diff review
        row = book.task("T1")
        self.assertEqual(("todo", 1, out.worktree),
                         (row["status"], row["rebuild_round"], row["rebuild_from"]))

    def test_a_gate_that_writes_into_its_checkout_fails_out_of_scope(self):
        # A green gate is not proof by itself: a gate that forges its own
        # evidence must be caught the same way a wandering builder is.
        fakes = Fakes()
        loop, book, _ = loop_for(evidence_task(gate="printf forged > a.py && true"), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("failed", out.state, out.why)
        self.assertIn("a.py", out.why)
        self.assertEqual("out_of_scope", book.task("T1")["status"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
