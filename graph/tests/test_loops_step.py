"""The step a loop is in, from the last line of its event log, and how durations read."""

import calendar
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import loops_list
import loops_step
import tmp_root  # noqa: F401

NOW = calendar.timegm((2026, 9, 28, 19, 40, 0))
AGE = 1860   # the process is 31 minutes old


def event(kind, at="2026-09-28T19:37:50Z", **fields):
    return json.dumps({"at": at, "kind": kind, **fields})


class Step(unittest.TestCase):
    def step(self, *lines, log=True):
        root = pathlib.Path(tempfile.mkdtemp())
        if log:
            (root / "events.jsonl").write_text("".join(line + "\n" for line in lines))
        return loops_step.step(str(root), AGE, NOW)

    def test_a_call_started_for_each_purpose_names_its_step(self):
        for purpose, name in (("grill", "grilling"), ("build", "building"), ("review", "reviewing")):
            with self.subTest(purpose=purpose):
                self.assertEqual((name, 130), self.step(event("lean_call_started", purpose=purpose)))

    def test_the_time_is_since_the_last_event_not_an_earlier_one(self):
        self.assertEqual(("building", 40), self.step(
            event("lean_call_started", "2026-09-28T19:30:00Z", purpose="grill"),
            event("lean_call_started", "2026-09-28T19:39:20Z", purpose="build")))

    def test_another_last_event_is_working(self):
        self.assertEqual(("working", 130), self.step(
            event("lean_call_started", "2026-09-28T19:30:00Z", purpose="build"), event("lean_suite")))

    def test_an_unknown_purpose_is_working(self):
        self.assertEqual(("working", 130), self.step(event("lean_call_started", purpose="plan")))
        self.assertEqual(("working", 130), self.step(event("lean_call_started")))

    def test_a_purpose_that_is_not_text_is_working_not_a_crash(self):
        for purpose in (["build"], {"a": 1}, 7, None):
            with self.subTest(purpose=purpose):
                self.assertEqual(("working", 130), self.step(event("lean_call_started", purpose=purpose)))

    def test_no_event_log_is_starting_for_as_long_as_the_process_has_run(self):
        self.assertEqual(("starting", AGE), self.step(log=False))

    def test_an_empty_event_log_is_starting(self):
        self.assertEqual(("starting", AGE), self.step())

    def test_a_broken_line_is_skipped(self):
        self.assertEqual(("building", 130), self.step(
            event("lean_call_started", purpose="build"), '{"at": "2026-09-28T19:39:00Z", "ki'))
        self.assertEqual(("starting", AGE), self.step("not json", "[1]", '{"kind": "x"}'))

    def test_a_workspace_that_cannot_be_read_is_starting(self):
        self.assertEqual(("starting", AGE), loops_step.step(None, AGE, NOW))
        self.assertEqual(("starting", AGE), loops_step.step("/no/such/workspace", AGE, NOW))

    def test_an_event_from_the_future_has_spent_no_time(self):
        self.assertEqual(("working", 0), self.step(event("lean_suite", "2026-09-28T19:41:00Z")))


class Duration(unittest.TestCase):
    def test_the_formats(self):
        self.assertEqual("45s", loops_list.duration(45))
        self.assertEqual("2m10s", loops_list.duration(130))
        self.assertEqual("1h05m", loops_list.duration(3900))

    def test_the_edges(self):
        self.assertEqual("1m00s", loops_list.duration(60))
        self.assertEqual("0s", loops_list.duration(0))
        self.assertEqual("59m59s", loops_list.duration(3599))
        self.assertEqual("1h00m", loops_list.duration(3600))


EXPECTED_TESTS = 12


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
