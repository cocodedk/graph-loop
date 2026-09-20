"""A gate that fails once is worth a second try in the SAME worktree: the next
pick continues where the first round left off, not from a fresh tree, and does
not re-pay red-first or the contract review. The rig lives in `test_loop`."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 3

GATE = "grep -q two a.py || (echo 'not yet two' && exit 1)"


class GateRebuildTest(unittest.TestCase):
    def test_a_first_gate_failure_is_rebuilt_in_the_same_worktree(self):
        fakes = Fakes(edit="still one\n")
        real = fakes.builder
        cwds: list[str] = []

        def builder(prompt, **kwargs):
            cwds.append(kwargs["cwd"])
            out = real(prompt, **kwargs)
            fakes.edit = "two\n"          # the next round writes the fix
            return out

        loop, book, space = loop_for(task(gate=GATE), fakes)
        loop.build = builder
        out = loop.run_task(book.task("T1"))
        self.assertEqual("failed", out.state)
        self.assertTrue(pathlib.Path(out.worktree).exists())
        queued = book.task("T1")
        self.assertEqual("todo", queued["status"])              # offered again
        self.assertEqual(1, queued["rebuild_round"])
        self.assertEqual(out.worktree, queued["rebuild_from"])
        self.assertIn("not yet two", queued["rejections"][-1])  # the gate's own reason, recorded

        calls_before = list(fakes.calls)
        again = loop.run_task(book.task("T1"))
        self.assertEqual("done", again.state)
        self.assertEqual(out.worktree, again.worktree)          # same worktree, not a fresh one
        self.assertEqual([out.worktree, out.worktree], cwds)    # the builder saw the same cwd both times
        # one build and ONE review (the diff): no contract review this round
        self.assertEqual(["build:work", "review"], fakes.calls[len(calls_before):])
        events = space.events()
        kinds = [row["kind"] for row in events]
        self.assertEqual(1, kinds.count("worktree"))            # created once, never again
        self.assertNotIn("rebuild_lost", kinds)                 # the tree was found, not lost
        # red-first ran for real once, round 0; round 1 is in the same
        # worktree, proved red before, so it is skipped, not re-run.
        red_first = [row for row in events
                    if row["kind"] == "step" and row.get("step") == "red_first"]
        self.assertEqual(1, len(red_first))
        self.assertEqual(1, kinds.count("skipped_red_first"))
        self.assertEqual("done", book.task("T1")["status"])


class OutageRebuildTest(unittest.TestCase):
    """An outage that spends no round (B4) still leaves `rebuild_from` set at
    round 0 — the next pick must reuse that tree, not cut a fresh one and
    re-pay the build the rule exists to save."""

    def test_a_round_zero_outage_is_rebuilt_in_the_same_worktree(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("capacity", text="unexpected status 404 Not Found, "
                                      "url: https://chatgpt.com/backend-api/codex/responses"),
                              Outcome("ok", verdict="ACCEPT", text="ok")])
        real = fakes.builder
        cwds: list[str] = []

        def builder(prompt, **kwargs):
            cwds.append(kwargs["cwd"])
            return real(prompt, **kwargs)

        loop, book, space = loop_for(task(), fakes)
        loop.build = builder
        first = loop.run_task(book.task("T1"))
        self.assertEqual("harness", first.state)
        self.assertFalse(book.task("T1").get("rebuild_round"))   # the outage spent no round
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertEqual(first.worktree, out.worktree)             # the same tree, reused
        # and ONE build: the retry resumes at the review the outage cut off
        # (finding 22), so there is no second builder call to re-pay.
        self.assertEqual([first.worktree], cwds)
        kinds = [row["kind"] for row in space.events()]
        self.assertEqual(1, kinds.count("worktree"))               # never cut a fresh one


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
