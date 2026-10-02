"""The lean loop writes `lean_call_started` just before each model call, so a long step shows.

The models are faked (`test_lean_run.Rig`); each fake looks at the event log when it is called."""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_run
import models
import review
import tmp_root  # noqa: F401
from providers import Outcome
from test_lean_run import ACCEPT, Rig

EXPECTED_TESTS = 6
BUILD = ("build", "rest-ring", models.LEAN["builder"]["effort"])
REPAIR = ("build", "rest-ring", models.LEAN["repair"]["effort"])
REVIEW = ("review", "rest-ring", models.LEAN["review"]["effort"])


class CallStarted(Rig):
    def setUp(self):
        super().setUp()
        self.seen = []                    # (call, the started events in the log when it was made)
        test = self

        class Reviews(list):
            def append(self, prompt):
                test.seen.append(("review", test.started()))
                super().append(prompt)
        self.reviews = Reviews()

    def started(self):
        return [(row["purpose"], row["task"], row["effort"]) for row in self.ws.events()
                if row["kind"] == "lean_call_started"]

    def watched(self, *writes):
        inner = self.builder(*writes)

        def build(ws, task, prompt, tree, resume="", effort=""):
            self.seen.append(("build", self.started()))
            return inner(ws, task, prompt, tree, resume, effort)
        return build

    def test_the_grill_is_announced_before_it_is_asked(self):
        def asked(*_args, **_kw):
            self.seen.append(("grill", self.started()))
            return Outcome("ok", verdict="ACCEPT")
        with mock.patch.object(review, "codex", asked):
            lean_run.grill(self.ws, self.repo, [str(self.spec)], "profile.md")
        self.assertEqual([("grill", [("grill", "grill", models.LEAN["review"]["effort"])])], self.seen)

    def test_the_build_and_the_review_are_announced_before_they_answer(self):
        self.run_it(self.watched(("ring.py", "amber\n")))
        self.assertEqual([("build", [BUILD]), ("review", [BUILD, REVIEW])], self.seen)

    def test_a_repair_says_so_with_its_own_effort(self):
        self.run_it(self.watched(("ring.py", "grey\n"), ("ring.py", "amber\n")), suites=(False, True))
        self.assertEqual([BUILD, REPAIR, REVIEW], self.started())
        self.assertEqual([("build", [BUILD]), ("build", [BUILD, REPAIR]),
                          ("review", [BUILD, REPAIR, REVIEW])], self.seen)
        self.assertEqual([BUILD[2], REPAIR[2]], self.efforts)   # the effort the builder was given

    def test_a_build_with_two_repairs_writes_three_build_events(self):
        self.run_it(self.watched(("ring.py", "a\n"), ("ring.py", "b\n"), ("ring.py", "c\n")),
                    suites=(False, False, True))
        self.assertEqual([BUILD, REPAIR, REPAIR, REVIEW], self.started())

    def test_a_run_that_stops_after_a_red_suite_writes_no_review_event(self):
        self.run_it(self.watched(("ring.py", "a\n"), ("ring.py", "b\n"), ("ring.py", "c\n")),
                    suites=(False, False, False), reviews=())
        self.assertEqual([BUILD, REPAIR, REPAIR], self.started())
        self.assertEqual([], self.reviews)

    def test_a_call_that_crashes_still_has_its_event(self):
        def crashed(ws, task, prompt, tree, resume="", effort=""):
            return Outcome("crash", text="the builder's process died")
        self.run_it(crashed, suites=(), reviews=(ACCEPT,))
        self.assertEqual([BUILD], self.started())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
