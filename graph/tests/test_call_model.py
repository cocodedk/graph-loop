"""The dashboard shows the model and the effort of the call a loop is making, from the last `lean_call_started`
event: the model is recorded now, and older events carry the effort alone. Anything else shows nothing."""

import calendar
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import loops_list
import loops_step
import models
import project_view
import providers
import tmp_root  # noqa: F401
from loops_ps import Loop
from test_lean_run import ACCEPT, Rig

EXPECTED_TESTS = 3
NOW = calendar.timegm((2026, 9, 28, 19, 40, 0))
HEAD = "    PID ELAPSED COMMAND\n"


def workspace(*events):
    folder = pathlib.Path(tempfile.mkdtemp())
    (folder / "events.jsonl").write_text("".join(json.dumps(row) + "\n" for row in events))
    return str(folder)


def call(**fields):
    return {"kind": "lean_call_started", "at": "2026-09-28T19:39:00Z", "purpose": "build", **fields}


class Recorded(Rig):
    def test_each_call_records_the_model_it_is_made_on(self):
        refused = providers.Outcome("ok", verdict="REJECT", text="a defect")
        self.run_it(self.builder(("ring.py", "grey\n"), ("ring.py", "amber\n")), suites=(True, True),
                    reviews=(refused, ACCEPT))
        called = [(row["purpose"], row["model"]) for row in self.ws.events() if row["kind"] == "lean_call_started"]
        build, review = models.LEAN["builder"]["model"], models.LEAN["review"]["model"]
        self.assertEqual([("build", build), ("review", review), ("build", build), ("review", review)], called)


class Read(unittest.TestCase):
    def test_the_model_and_effort_of_the_running_call_or_the_effort_alone_or_nothing(self):
        self.assertEqual("brand-1 e-hi", loops_step.using(workspace(call(model="claude-brand-1", effort="e-hi"))))
        self.assertEqual("other-2 e-x", loops_step.using(workspace(call(model="other-2", effort="e-x"))))
        self.assertEqual("e-hi", loops_step.using(workspace(call(effort="e-hi"))))                   # an older event
        self.assertEqual("", loops_step.using(workspace({"kind": "lean_suite", "at": "2026-09-28T19:39:00Z"})))
        self.assertEqual("", loops_step.using(workspace()))
        self.assertEqual("", loops_step.using(None))


class Shown(unittest.TestCase):
    def test_the_list_and_the_project_line_show_it_and_are_unchanged_without_it(self):
        with_model = workspace(call(model="claude-brand-1", effort="e-hi"))
        without = workspace({"kind": "lean_suite", "at": "2026-09-28T19:39:00Z"})
        ps = "".join(f"{pid} 100 python3 graph/lean.py --workspace {w} --repo /work/p{pid} --spec docs/lean/0{pid}-a.md\n"
                     for pid, w in ((1, with_model), (2, without)))
        lines = loops_list.report(HEAD + ps, lambda pid: "/work", NOW).splitlines()
        self.assertIn("brand-1 e-hi", lines[0])
        self.assertNotIn("brand", lines[1])
        self.assertTrue(lines[0].endswith("loop up 1m40s"))
        loop = Loop(1, 100, "p1", "01-a", with_model)
        report = project_view.report(tempfile.mkdtemp(), [loop], NOW, None)
        self.assertIn("loop: 01-a building 1m00s  brand-1 e-hi", report)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
