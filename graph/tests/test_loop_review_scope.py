"""The diff boundary separates observations and retries malformed reviews without building."""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from providers import Outcome
from test_loop import Fakes, loop_for, task
from test_review_scope import answer, finding

EXPECTED_TESTS = 5
ACCEPT = Outcome("ok", verdict="ACCEPT", text="ok")


def scripted(text: str, verdict="ACCEPT"):
    return Fakes(review=[ACCEPT, Outcome("ok", verdict=verdict, text=text), ACCEPT])


class ScopedReviewTest(unittest.TestCase):
    def test_blocked_footer_parks_before_diff_validation_or_rebuild(self):
        import tempfile
        from types import SimpleNamespace
        from unittest import mock

        from distress import INSTRUCTION, TEMPLATE
        from loop_diff_review import review_change
        from resources import Resource
        from review import _claude_review
        from test_distress import BLOCKED, DONE
        from test_replan import book_with
        from workspace import Workspace
        for footer in (BLOCKED, DONE.replace('false, "why": ""',
                       'true, "why": "missing inputs"')):
            book = book_with(status="todo")
            space = Workspace(tempfile.mkdtemp())
            tree = mock.Mock(path="unused", commit="base")
            tree.diff.return_value = "+two"
            text = answer() + "\n" + footer
            with mock.patch("providers.claude", return_value=Outcome("ok", text=text)) as call:
                loop = SimpleNamespace(backlog=book, space=space, review=lambda prompt, **_:
                    _claude_review(prompt, Resource("claude", "work", "opus"), "high", 1))
                out = review_change(loop, book.task("T1"), tree, 0)
            self.assertEqual("blocked", out.state)
            self.assertEqual("blocked_by_agent", book.task("T1")["status"])
            self.assertFalse(book.startable())
            self.assertFalse(book.task("T1").get("rebuild_round"))
            self.assertEqual(out.why, next(e["why"] for e in space.events()
                                          if e["kind"] == "needs_a_person"))
            self.assertIn(INSTRUCTION + TEMPLATE, call.call_args.args[1])
        from review_read import _read_review
        self.assertEqual(("ACCEPT", answer()), _read_review(answer() + "\n" + DONE))


    def test_observations_are_recorded_and_the_task_finishes_without_a_rebuild(self):
        fakes = scripted(answer(observations=["Separate old-module cleanup"]))
        loop, book, space = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertFalse(book.task("T1").get("rejections"))
        self.assertFalse(book.task("T1").get("rebuild_round"))
        recorded = list((space.root / "calls" / "T1").glob("*diff-review-observations*"))
        self.assertEqual(1, len(recorded))
        self.assertEqual(["Separate old-module cleanup"], json.loads(recorded[0].read_text()))
        self.assertEqual(["review", "build:work", "review"], fakes.calls)
        self.assertNotIn("T1", [row["id"] for row in book.startable()])

    def test_only_the_blocker_goes_back_to_the_builder(self):
        text = answer([finding(diff_line=7)], ["Separate old-module cleanup"])
        fakes = scripted(text, "REJECT")
        loop, book, _ = loop_for(task(), fakes)
        self.assertEqual("rejected", loop.run_task(book.task("T1")).state)
        reasons = "\n".join(book.task("T1")["rejections"])
        self.assertIn("Wrong value", reasons)
        self.assertIn("The changed value fails the declared result", reasons)
        self.assertNotIn("Separate old-module cleanup", reasons)
        self.assertEqual("done", loop.run_task(book.task("T1")).state)
        self.assertNotIn("Separate old-module cleanup", fakes.prompts[-1])

    def test_bad_anchor_preserves_finished_gate_and_retries_only_the_review(self):
        fakes = scripted(answer([finding(diff_line=1)]), "REJECT")
        loop, book, _ = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        self.assertEqual("gate", book.task("T1")["finished"]["phase"])
        self.assertNotIn("Wrong value", "\n".join(book.task("T1")["rejections"]))
        self.assertEqual("done", loop.run_task(book.task("T1")).state)
        self.assertEqual(["review", "build:work", "review", "review"], fakes.calls)

    def test_a_legacy_diff_answer_cannot_bypass_the_boundary(self):
        fakes = Fakes()
        loop, book, _ = loop_for(task(), fakes)
        loop.review = lambda *args, **kwargs: Outcome("ok", verdict="ACCEPT", text="REVIEW: ACCEPT")
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        self.assertEqual("gate", book.task("T1")["finished"]["phase"])
        self.assertNotEqual("done", book.task("T1")["status"])


class CountTest(unittest.TestCase):
    def test_count(self):
        suite = unittest.TestLoader().discover(str(pathlib.Path(__file__).parent),
                                              pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, suite.countTestCases())


if __name__ == "__main__":
    unittest.main()
