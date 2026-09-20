"""The plan phase's calls are not the build phase's failures.

The futility ceiling asks one question — is the build landing work? — and
answers it by counting answered attempts since the last progress. With the
phases split, a campaign plans first and builds afterwards in the same
campaign directory, and every paid slicer call of the plan phase sat in that
window. The third campaign's build tripped after exactly two card failures:

    FUTILE: 31 answered attempts since progress (ceiling 12)

29 of those 31 were planning. A build entered its own phase with its budget
already spent, and twelve is not a ceiling a build can ever see when planning
spent twenty-nine (2026-09-18).

Planning is not the build going nowhere, so it is not in the window. The
slicer's calls say so on themselves — `purpose="plan"` — rather than being told
apart by the task name they happen to carry.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from watchdog import check
from workspace import Workspace

EXPECTED_TESTS = 4


def space() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog="b.yaml")


class PlanningIsNotTheBuildGoingNowhere(unittest.TestCase):
    def test_a_plan_phase_does_not_spend_the_build_ceiling(self):
        here = space()
        for _ in range(29):
            here.attempt("the slicer", account="plan", kind="ok", purpose="plan")
        for _ in range(2):
            here.attempt("T1", account="work", kind="ok")
        self.assertFalse(check(here, attempt_ceiling=12).futile)

    def test_the_build_still_trips_on_its_own_calls(self):
        here = space()
        for _ in range(29):
            here.attempt("the slicer", account="plan", kind="ok", purpose="plan")
        for _ in range(12):
            here.attempt("T1", account="work", kind="ok")
        verdict = check(here, attempt_ceiling=12)
        self.assertTrue(verdict.futile)
        self.assertIn("12 answered attempts", verdict.why)   # its own, not the plan's

    def test_cards_planned_is_progress_so_the_hours_window_starts_at_the_build(self):
        # The same defect in the other window: three hours of planning, then
        # one build step, used to read as three hours of the build going
        # nowhere before the build had done anything.
        class Rows:
            def events(self):
                return [{"kind": "step", "task": "the slicer", "step": "slice",
                         "seconds": 3600, "at": f"2026-09-18T{10 + n}:00:00Z"}
                        for n in range(3)] + [
                    {"kind": "planned", "task": "the plan", "added": ["T1"],
                     "at": "2026-09-18T13:00:00Z"},
                    {"kind": "step", "task": "T1", "step": "build", "seconds": 60,
                     "at": "2026-09-18T13:01:00Z"}]
        self.assertFalse(check(Rows(), hours_ceiling=2.0).futile)


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS, found)


if __name__ == "__main__":
    unittest.main()
