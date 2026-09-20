"""Harness faults after paid work: a broken review or a broken build call
continues in the kept worktree as a counted round (B4), while a refusal that
provably spent nothing waits without spending a round. The rig is `test_loop`'s."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 13


class BrokenReviewTest(unittest.TestCase):
    """A review that did not happen is a harness fault, never a refusal.

    Seen live: a reviewer was killed, its banner was parsed as the answer, and
    three good tasks were quarantined for a rejection nobody wrote.
    """

    def test_a_review_that_crashed_does_not_refuse_the_task(self):
        fakes = Fakes(review=[Outcome("crash", text="the review did not return")])
        loop, book, _ = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        self.assertEqual("todo", book.task("T1")["status"])

    def test_a_reviewer_at_its_usage_limit_does_not_refuse_the_task(self):
        fakes = Fakes(review=[Outcome("limit", text="usage limit")])
        loop, book, _ = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        self.assertEqual("todo", book.task("T1")["status"])

    def test_a_broken_review_of_the_diff_keeps_the_work_for_a_retry(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("malformed", text="banner only")])
        loop, book, _ = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        # gate-green work: queued as a counted round in the SAME tree, so the
        # next pick re-reviews there instead of re-paying the build (B4)
        row = book.task("T1")
        self.assertEqual(("todo", 1, out.worktree),
                         (row["status"], row["rebuild_round"], row["rebuild_from"]))
        self.assertIn("diff review did not happen", row["rejections"][-1])

    def test_a_limit_hit_part_way_through_keeps_the_paid_work_in_place(self):
        # The cost proves the call worked before the limit cut it off: the belt
        # stops (another account would re-pay the same work) and the tree
        # continues as a counted round, never "waiting" with the work removed.
        fakes = Fakes(build=[Outcome("limit", text="limit reached mid-call", cost=1.2, tokens=500),
                             Outcome("limit", text="never called")])
        loop, book, _ = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        row = book.task("T1")
        self.assertEqual(("todo", 1, out.worktree),
                         (row["status"], row["rebuild_round"], row["rebuild_from"]))
        self.assertEqual(1, len([c for c in fakes.calls if c.startswith("build")]))

    def test_an_unavailable_review_stops_at_the_same_cap_as_a_rejected_diff(self):
        # the worktree is lost, so this round reviews the contract again (ACCEPT)
        # before the diff review breaks — at round three, the cap holds
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("malformed", text="banner only")])
        loop, book, _ = loop_for(task(rebuild_round=2, rebuild_from=""), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", out.state)
        row = book.task("T1")
        self.assertEqual(("rejected", 3), (row["status"], row["rebuild_round"]))
        self.assertIn("did not happen", row["refused_why"])

    def test_an_unknown_limit_that_changed_nothing_is_a_refusal_not_paid_work(self):
        # Missing figures mean unknown, not innocent: the judge is the tree.
        # edit=None models a refusal that left no edit behind — the belt walks
        # and the queue stands, never a counted round on a weekend limit.
        fakes = Fakes(build=[Outcome("limit", text="usage limit reached"),
                             Outcome("limit", text="usage limit reached")], edit=None)
        loop, book, _ = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("waiting", out.state)
        row = book.task("T1")
        self.assertEqual("todo", row["status"])
        self.assertFalse(row.get("rebuild_round"))
        self.assertEqual(2, len([c for c in fakes.calls if c.startswith("build")]))

    def test_an_unknown_limit_that_edited_the_tree_is_paid_work_kept_in_place(self):
        # The same figureless limit, but the call edited a file before dying:
        # the diff is the proof — the belt stops and the round is counted.
        import pathlib
        fakes = Fakes()
        loop, book, _ = loop_for(task(), fakes)
        builds = []

        def builder(prompt, *, cwd, **kw):
            builds.append(cwd)
            (pathlib.Path(cwd) / "a.py").write_text("half-done\n")
            return Outcome("limit", text="limit mid-call, no figures")

        loop.build = builder
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        row = book.task("T1")
        self.assertEqual(("todo", 1, out.worktree),
                         (row["status"], row["rebuild_round"], row["rebuild_from"]))
        self.assertEqual(1, len(builds))                        # the belt stopped

    def test_a_diff_review_outage_spends_no_round(self):
        # The reviewer itself was never reached. Recorded 2026-09-03: one
        # review attempt, 15:02:59Z-15:03:13Z, ended on the reviewer's 404 —
        # not a finding about the work, so no round is spent.
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("capacity", text="unexpected status 404 Not Found, "
                                      "url: https://chatgpt.com/backend-api/codex/responses")])
        loop, book, space = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        row = book.task("T1")
        self.assertEqual(("todo", out.worktree), (row["status"], row["rebuild_from"]))
        self.assertFalse(row.get("rebuild_round"))
        queued = [r for r in space.events() if r.get("kind") == "rebuild_queued"][-1]
        self.assertFalse(queued["charged"])
        self.assertIn("capacity", queued["why"])


class ContractFaultTest(unittest.TestCase):
    """A rebuild round's contract is read again only once its digest goes
    stale (a goal edited after round one's ACCEPT); its outage and its
    refusal must not delete the tree round one already paid for (2026-09-01:
    a round-2 contract REJECT deleted a 20-minute build)."""

    def test_a_rebuild_rounds_contract_refusal_keeps_the_tree(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line")])
        loop, book, _ = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        book.set_status("T1", "todo", goal="a different goal")   # stale digest: round 2 rereads the contract
        fakes.review = [Outcome("ok", verdict="REJECT", text="not this goal")]
        out = loop.run_task(book.task("T1"))
        self.assertEqual("refused", out.state)
        self.assertTrue((pathlib.Path(first.worktree) / ".git").exists())
        self.assertEqual(first.worktree, book.task("T1")["rebuild_from"])

    def test_a_rebuild_rounds_contract_outage_continues_in_place(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line")])
        loop, book, _ = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        book.set_status("T1", "todo", goal="a different goal")   # stale digest: round 2 rereads the contract
        fakes.review = [Outcome("crash", text="the review did not return")]
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        row = book.task("T1")
        self.assertEqual(("todo", 2, first.worktree),
                         (row["status"], row["rebuild_round"], row["rebuild_from"]))
        self.assertTrue(pathlib.Path(first.worktree).exists())

    def test_a_rebuild_rounds_contract_outage_by_limit_spends_no_round(self):
        # Same stale-digest reread as above, but the reviewer's own account hit
        # its usage limit — the belt would try another, so this never spends
        # the round a crash or a malformed answer would (B4's carve-out).
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line")])
        loop, book, space = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        book.set_status("T1", "todo", goal="a different goal")
        fakes.review = [Outcome("limit", text="usage limit")]
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        row = book.task("T1")
        self.assertEqual(("todo", 1, first.worktree),
                         (row["status"], row["rebuild_round"], row["rebuild_from"]))
        queued = [r for r in space.events() if r.get("kind") == "rebuild_queued"][-1]
        self.assertFalse(queued["charged"])
        self.assertIn("limit", queued["why"])

    def test_a_first_round_refusal_still_removes_the_tree(self):
        fakes = Fakes(review=[Outcome("ok", verdict="REJECT", text="1. too broad")])
        loop, book, space = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("refused", out.state)
        made = [r["path"] for r in space.events() if r.get("kind") == "worktree"][-1]
        self.assertFalse(pathlib.Path(made).exists())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
