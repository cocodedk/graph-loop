"""What the log has to answer: where the time went, where the money went, what refused.

Written before `report.py`. A campaign that cannot say which step is the
bottleneck cannot be made faster, so every step is timed and every refusal keeps
its reason.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from report import report
from workspace import Workspace

EXPECTED_TESTS = 14


def space() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog="b.yaml")


class TimingTest(unittest.TestCase):
    def test_a_step_records_how_long_it_took(self):
        here = space()
        with here.step("T1", "build"):
            time.sleep(0.05)
        row = [r for r in here.events() if r["kind"] == "step"][-1]
        self.assertEqual(("T1", "build"), (row["task"], row["step"]))
        self.assertGreaterEqual(row["seconds"], 0.05)

    def test_a_step_that_raises_is_still_recorded_and_says_so(self):
        here = space()
        with self.assertRaises(ValueError), here.step("T1", "gate"):
            raise ValueError("boom")
        row = [r for r in here.events() if r["kind"] == "step"][-1]
        self.assertEqual("gate", row["step"])
        self.assertIn("boom", row["error"])

    def test_a_step_carries_the_outcome_the_caller_names(self):
        here = space()
        with here.step("T1", "review") as note:
            note(verdict="REJECT", why="too broad")
        row = [r for r in here.events() if r["kind"] == "step"][-1]
        self.assertEqual(("REJECT", "too broad"), (row["verdict"], row["why"]))


class ArtefactTest(unittest.TestCase):
    def test_every_prompt_answer_and_gate_output_is_written_down(self):
        here = space()
        where = here.artifact("T1", "build-prompt", "do the thing")
        self.assertTrue(pathlib.Path(where).exists())
        self.assertEqual("do the thing", pathlib.Path(where).read_text())
        row = [r for r in here.events() if r["kind"] == "artifact"][-1]
        self.assertEqual(("T1", "build-prompt"), (row["task"], row["name"]))
        self.assertEqual(where, row["path"])

    def test_two_artifacts_of_the_same_name_never_overwrite_each_other(self):
        here = space()
        first = here.artifact("T1", "answer", "one")
        second = here.artifact("T1", "answer", "two")
        self.assertNotEqual(first, second)
        self.assertEqual("one", pathlib.Path(first).read_text())


class ReportTest(unittest.TestCase):
    def _campaign(self) -> Workspace:
        here = space()
        for task, step, seconds in (("T1", "red_first", 4.0), ("T1", "contract", 30.0),
                                    ("T1", "build", 60.0), ("T1", "gate", 12.0),
                                    ("T1", "diff_review", 40.0),
                                    ("T2", "red_first", 2.0), ("T2", "contract", 25.0)):
            here.event("step", task=task, step=step, seconds=seconds)
        here.attempt("T1", account="work", kind="ok", cost=0.19, tokens=455)
        here.attempt("T2", account="work", kind="limit")
        here.event("refused", task="T2", step="contract", why="the gate can pass hard-coded")
        return here

    def test_the_report_names_the_step_that_costs_the_most_time(self):
        out = report(self._campaign())
        self.assertEqual("build", out["slowest_step"])          # 60s, one call
        self.assertAlmostEqual(55.0, out["by_step"]["contract"]["seconds"])  # 30 + 25
        self.assertEqual(2, out["by_step"]["contract"]["calls"])

    def test_it_gives_each_step_its_share_of_the_clock(self):
        out = report(self._campaign())
        self.assertAlmostEqual(100.0, sum(row["share"] for row in out["by_step"].values()),
                               places=1)
        self.assertGreater(out["by_step"]["contract"]["share"],
                           out["by_step"]["gate"]["share"])

    def test_it_separates_time_spent_on_work_from_time_spent_refusing(self):
        out = report(self._campaign())
        self.assertAlmostEqual(72.0, out["seconds_on_work"])     # build + gate
        self.assertAlmostEqual(101.0, out["seconds_on_judging"])  # reviews + red-first

    def test_it_counts_what_was_refused_and_why(self):
        out = report(self._campaign())
        self.assertEqual(1, out["refusals"])
        self.assertIn("hard-coded", out["refusal_reasons"][0])

    def test_the_text_leads_with_refusals_since_the_last_accepted_card(self):
        # the lifetime total only grows and reads as alarm; the number that is
        # news is what happened since the loop last landed work
        from report import as_text
        here = self._campaign()
        here.event("accepted", task="T1", worktree="/tmp/x", commit="abc")
        here.event("refused", task="T2", step="contract", why="one more after the accept")
        text = as_text(report(here))
        self.assertIn("refusals since the last accepted card: 1", text)
        self.assertIn("has seen 2", text)                       # lifetime stays history
        self.assertIn("history, not news", text)

    def test_before_any_acceptance_refusals_are_current_not_history(self):
        from report import as_text
        text = as_text(report(self._campaign()))                # the fixture never accepts
        self.assertIn("refusals since the campaign start: 1", text)
        self.assertIn("nothing accepted yet", text)
        self.assertNotIn("history, not news", text)

    def test_a_rejection_queued_for_another_round_still_counts_as_one(self):
        here = self._campaign()
        here.event("rebuild_queued", task="T1", round=1, why="the test loosens the count")
        out = report(here)
        self.assertEqual(2, out["refusals"])
        self.assertTrue(any("loosens" in why for why in out["refusal_reasons"]))

    def test_it_reports_known_spend_and_the_calls_that_did_not_count(self):
        out = report(self._campaign())
        self.assertAlmostEqual(0.19, out["spend_known"])
        self.assertEqual(1, out["uncounted_calls"])  # the usage limit did not count as an attempt


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
