"""An in-place round's red-first that finds the gate already green: the
previous round's work stands, so the diff review decides -- never a park.
Mirrors test_loop_rebuild.py's in-place setup. The rig lives in test_loop."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from loop import Loop
from providers import Outcome
from test_loop import Fakes, loop_for, repo_with, task

EXPECTED_TESTS = 5


class GateGreenInPlaceTest(unittest.TestCase):
    def test_a_green_gate_in_place_with_no_open_finding_still_reaches_the_builder(self):
        # Round 0: the fix lands but round 0's diff review flags the GATE's
        # own wording as too loose, queuing a rebuild round in the SAME
        # worktree. Between rounds a doctor rewrites the gate to fix that
        # wording and marks the card gate_reviewed_first -- round 1's
        # red-first is not skipped: it runs for real and finds the (new)
        # gate green. No production writer ever clears a queued finding
        # (every rebuild write only appends one), so a round that starts
        # with none recorded -- same as a card parked green_already live --
        # is not proof the work is done: the builder still gets the round,
        # an empty finding list and all, and judge() reads what it produces.
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT",
                                      text="1. the gate's grep pattern is too loose"),
                              Outcome("ok", verdict="ACCEPT", text="ok")])
        root, book, space = repo_with(task())
        loop = Loop(repo=root, backlog=book, space=space, build=fakes.builder,
                    review=fakes.reviewer, branch="campaign/test")
        first = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", first.state)

        # the doctor's rewrite: a stricter, still-passing gate; no finding
        # carried into round 1 (nothing here claims a writer cleared one)
        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        gate="grep -qx two a.py",
                        gate_reviewed_first=True, rejections=[], refused_why=None)
        calls_before = list(fakes.calls)
        again = loop.run_task(book.task("T1"))

        self.assertEqual("done", again.state, again.why)
        self.assertEqual(first.worktree, again.worktree)   # same tree, not rebuilt fresh
        # contract review (red_first's gate_reviewed_first path), the builder
        # with nothing to act on, then the diff review inside judge
        self.assertEqual(["review", "build:work", "review"], fakes.calls[len(calls_before):])
        row = book.task("T1")
        self.assertEqual("done", row["status"])
        self.assertTrue(row.get("commit"))                 # a keeper commit, not a park
        kinds = [r["kind"] for r in space.events() if r.get("task") == "T1"]
        self.assertIn("gate_green_in_place", kinds)

    def test_a_green_gate_in_place_that_writes_outside_its_files_ends_out_of_scope(self):
        # Same shortcut, but this round's gate -- reviewed once, like any
        # rewrite -- also touches a file outside the task's own when
        # red_first runs it to check for red. Jumping straight to judge()
        # must not miss that: it is the same check build() applies to every
        # ordinary round, and skipping it let a green gate's side effect
        # through as done.
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line"),
                              Outcome("ok", verdict="ACCEPT", text="ok")])
        loop, book, space = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", first.state)

        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        gate="grep -q two a.py && touch outside.txt",
                        gate_reviewed_first=True, rejections=[], refused_why=None)
        again = loop.run_task(book.task("T1"))

        self.assertEqual("failed", again.state, again.why)
        self.assertIn("outside.txt", again.why)
        self.assertEqual("out_of_scope", book.task("T1")["status"])
        scoped = [r for r in space.events()
                 if r.get("task") == "T1" and r["kind"] == "failed"]
        self.assertEqual("scope", scoped[-1].get("step"))

    def test_a_green_gate_in_place_whose_second_run_writes_outside_ends_out_of_scope(self):
        # Same shortcut, but this round's gate is clean on the FIRST run --
        # the one red_first uses to find it already green -- and writes
        # outside.txt only on its SECOND run, the one judge() makes itself.
        # A marker OUTSIDE the tree (never a scope violation of its own)
        # tells the gate which run it is. Before the HEAD/scope guard moved
        # inside judge(), only that first, clean run was ever checked, so
        # this fault sailed through as done.
        marker = str(pathlib.Path(tempfile.mkdtemp()) / "ran.marker")
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line"),
                              Outcome("ok", verdict="ACCEPT", text="ok")])
        loop, book, space = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", first.state)

        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        gate=(f"test -e {marker} && touch outside.txt; "
                              f"touch {marker}; grep -q two a.py"),
                        gate_reviewed_first=True, rejections=[], refused_why=None)
        again = loop.run_task(book.task("T1"))

        self.assertEqual("failed", again.state, again.why)
        self.assertIn("outside.txt", again.why)
        self.assertEqual("out_of_scope", book.task("T1")["status"])
        scoped = [r for r in space.events()
                 if r.get("task") == "T1" and r["kind"] == "failed"]
        self.assertEqual("scope", scoped[-1].get("step"))

    def test_a_green_gate_in_place_with_an_open_finding_still_sends_it_back_to_the_builder(self):
        # Same shortcut, but round 1 still carries an unresolved finding: the
        # green gate is the PREVIOUS round's work standing, not proof this
        # one is fixed, so the builder gets one more call with the finding
        # in hand before the tree is judged.
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line"),
                              Outcome("ok", verdict="ACCEPT", text="ok")])
        loop, book, _ = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", first.state)

        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        gate_reviewed_first=True, rejections=["1. wrong line"], refused_why=None)
        prompts: list[str] = []
        real = fakes.builder

        def builder(prompt, **kwargs):
            prompts.append(prompt)
            return real(prompt, **kwargs)

        loop.build = builder
        calls_before = list(fakes.calls)
        again = loop.run_task(book.task("T1"))

        self.assertEqual("done", again.state, again.why)
        self.assertEqual(["review", "build:work", "review"], fakes.calls[len(calls_before):])
        self.assertIn("wrong line", prompts[0])            # the open finding reached the builder
        self.assertEqual("done", book.task("T1")["status"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
