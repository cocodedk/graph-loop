"""Resume the phase that did not finish (Astra's finding 22).

A reviewer outage after a green gate used to send work that already stands
through another builder call. The card remembers the phase that finished, the
tree, the contract and the diff; a retry that matches all four re-runs only the
missing review. Anything different falls back to the ordinary path. The rig is
`test_loop`'s.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 6

OUTAGE = Outcome("capacity", text="unexpected status 404 Not Found")
ACCEPT = Outcome("ok", verdict="ACCEPT", text="ok")


class ResumeTest(unittest.TestCase):
    def test_a_review_outage_after_a_green_gate_costs_no_builder_call(self):
        """The gate was green in this tree and only the diff review is missing:
        the retry reviews, and pays no builder."""
        fakes = Fakes(review=[ACCEPT, OUTAGE, ACCEPT])
        loop, book, space = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        self.assertEqual("harness", first.state)
        before = len(fakes.calls)

        again = loop.run_task(book.task("T1"))
        self.assertEqual("done", again.state, again.why)
        self.assertEqual(first.worktree, again.worktree)
        self.assertEqual(["review"], fakes.calls[before:])   # the review alone
        self.assertIn("resumed", [row["kind"] for row in space.events()])
        self.assertNotIn("finished", book.task("T1"))        # read once, then gone


class FallbackTest(unittest.TestCase):
    def test_a_tree_edited_in_between_runs_the_ordinary_path(self):
        """The record stands for a tree as it was left. Once it differs, what
        the gate and the reviewer would judge is not what finished."""
        fakes = Fakes(review=[ACCEPT, OUTAGE, ACCEPT])
        loop, book, _ = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        (pathlib.Path(first.worktree) / "a.py").write_text("two two\n")   # still green
        before = len(fakes.calls)

        again = loop.run_task(book.task("T1"))
        self.assertEqual("done", again.state, again.why)
        self.assertEqual(["build:work", "review"], fakes.calls[before:])


class MovedBaseTest(unittest.TestCase):
    def test_a_moved_base_runs_the_ordinary_path_even_when_the_diff_reads_the_same(self):
        """A tree advanced onto a new base is not the tree the gate passed in.
        What landed since sits beside the work now, and when it touched other
        files the diff comes back word for word the same — so the diff alone
        cannot notice the move, and the base the round started from is part of
        the record."""
        fakes = Fakes(review=[ACCEPT, OUTAGE, ACCEPT])
        loop, book, space = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        self.assertEqual("harness", first.state)
        (pathlib.Path(loop.repo) / "b.py").write_text("elsewhere\n")   # unrelated work lands on the base
        for args in (("git", "add", "b.py"), ("git", "commit", "-qm", "elsewhere")):
            subprocess.run(args, cwd=loop.repo, capture_output=True, check=True)
        before = len(fakes.calls)

        again = loop.run_task(book.task("T1"))
        self.assertEqual("done", again.state, again.why)
        self.assertIn("tree_rebased", [row["kind"] for row in space.events()])
        self.assertEqual(["build:work", "review"], fakes.calls[before:])


class ContractOutageTest(unittest.TestCase):
    def test_a_contract_outage_records_no_finished_phase(self):
        """The contract review's own outage reaches the same retry, and its
        gate has not run this round: nothing to resume."""
        fakes = Fakes(review=[ACCEPT, Outcome("ok", verdict="REJECT", text="1. wrong line")])
        loop, book, _ = loop_for(task(), fakes)
        loop.run_task(book.task("T1"))
        book.set_status("T1", "todo", goal="a different goal")   # stale digest: the contract is reread
        fakes.review = [OUTAGE]
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        self.assertNotIn("finished", book.task("T1"))


class LiveCardTest(unittest.TestCase):
    def test_a_live_card_records_no_finished_phase(self):
        """A live gate performs the work it measures, and a live round that ends
        anywhere but done is held for a person: nothing here resumes itself, and
        a resumed round would skip the `live_call_open` the builder step writes."""
        fakes = Fakes(review=[ACCEPT, OUTAGE])
        loop, book, _ = loop_for(task(gate_has_side_effects=True, gate="true",
                                      helper_verbs=["journal"]), fakes)
        loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertEqual("live_turn_ended", row["status"])
        self.assertNotIn("finished", row)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
