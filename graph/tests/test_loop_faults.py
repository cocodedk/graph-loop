"""Provider outages keep paid work without charging a round; other harness
faults still spend a bounded round. The rig is `test_loop`'s."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 14


class BrokenReviewTest(unittest.TestCase):
    """A review that did not happen is a harness fault, never a refusal."""

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
        row = book.task("T1")
        self.assertEqual(("todo", 1, out.worktree),
                         (row["status"], row["rebuild_round"], row["rebuild_from"]))
        self.assertIn("diff review did not happen", row["rejections"][-1])

    def test_a_limit_hit_part_way_through_keeps_the_paid_work_in_place(self):
        for kind in ("limit", "auth", "capacity"):
            for rounds in (0, 2):
                with self.subTest(kind=kind, rounds=rounds):
                    fakes = Fakes(build=[Outcome(kind, text="provider unavailable", cost=1.2,
                                                  tokens=500, session="kept-session")])
                    loop, book, space = loop_for(task(rebuild_round=rounds,
                                                      rejections=["unresolved diff finding"]), fakes)
                    out = loop.run_task(book.task("T1"))
                    row = book.task("T1")
                    self.assertEqual("harness", out.state)
                    self.assertEqual(("todo", rounds, out.worktree),
                                     (row["status"], row.get("rebuild_round", 0), row["rebuild_from"]))
                    self.assertEqual("kept-session", row["session"])
                    self.assertEqual("unresolved diff finding", row["rejections"][0])
                    self.assertEqual(1, len([c for c in fakes.calls if c.startswith("build")]))
                    queued = [r for r in space.events() if r.get("kind") == "rebuild_queued"][-1]
                    self.assertIs(False, queued["charged"])

    def test_a_builder_crash_or_malformed_answer_still_reaches_the_round_cap(self):
        for kind in ("crash", "malformed"):
            with self.subTest(kind=kind):
                fakes = Fakes(build=[Outcome(kind, text="broken answer", cost=1.2, tokens=500)])
                loop, book, _ = loop_for(task(rebuild_round=2), fakes)
                out = loop.run_task(book.task("T1"))
                self.assertEqual("rejected", out.state)
                self.assertEqual(("rejected", 3), (book.task("T1")["status"], book.task("T1")["rebuild_round"]))

    def test_an_unavailable_review_stops_at_the_same_cap_as_a_rejected_diff(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("malformed", text="banner only")])
        loop, book, _ = loop_for(task(rebuild_round=2, rebuild_from=""), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", out.state)
        row = book.task("T1")
        self.assertEqual(("rejected", 3), (row["status"], row["rebuild_round"]))
        self.assertIn("did not happen", row["refused_why"])

    def test_an_unknown_limit_that_changed_nothing_is_a_refusal_not_paid_work(self):
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
        # The diff proves work happened; the provider's limit still spends no round.
        fakes = Fakes()
        loop, book, space = loop_for(task(), fakes)
        builds = []

        def builder(prompt, *, cwd, **kw):
            builds.append(cwd)
            (pathlib.Path(cwd) / "a.py").write_text("half-done\n")
            return Outcome("limit", text="limit mid-call, no figures")

        loop.build = builder
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        row = book.task("T1")
        self.assertEqual(("todo", 0, out.worktree),
                         (row["status"], row.get("rebuild_round", 0), row["rebuild_from"]))
        self.assertEqual(1, len(builds))                        # the belt stopped
        self.assertEqual("half-done\n", (pathlib.Path(out.worktree) / "a.py").read_text())
        queued = [r for r in space.events() if r.get("kind") == "rebuild_queued"][-1]
        self.assertIs(False, queued["charged"])

    def test_a_diff_review_outage_spends_no_round(self):
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
    """A stale contract must be read again without losing earlier paid work."""

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
