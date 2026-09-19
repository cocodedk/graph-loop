"""Cards run side by side: several code cards at once, a live card alone, and
one writer at a time on the task list."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import threading
import unittest
import unittest.mock

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(HERE))

from backlog import Backlog
from backlog_status import runs_alone
from loop_types import TaskOutcome
from turn import run_lanes
from workspace import Workspace

EXPECTED_TESTS = 10


def book_of(*ids) -> Backlog:
    rows = [{"id": i, "goal": "g", "status": "todo", "needs": [], "files": ["a.py"],
             "gate": "true", "done_when": "x"} for i in ids]
    path = pathlib.Path(tempfile.mkdtemp()) / "b.yaml"
    path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": rows}, sort_keys=False))
    return Backlog(path)


class FakeLoop:
    def __init__(self, hold: threading.Event | None = None):
        self.seen: list = []
        self.at_once = 0
        self.most = 0
        self.hold = hold
        self.lock = threading.Lock()

    def run_task(self, task):
        with self.lock:
            self.at_once += 1
            self.most = max(self.most, self.at_once)
        if self.hold:
            self.hold.wait(2)
        with self.lock:
            self.at_once -= 1
            self.seen.append(task["id"])
        return TaskOutcome("done", "")


class LanesTest(unittest.TestCase):
    def test_three_cards_run_at_the_same_time(self):
        hold = threading.Event()
        loop = FakeLoop(hold)
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        book = book_of("T1", "T2", "T3")
        threading.Timer(0.3, hold.set).start()
        ran, outside = run_lanes(loop, book, space, book.tasks())
        self.assertEqual(3, ran)
        self.assertEqual(3, loop.most)          # all three at once, not one after another
        self.assertFalse(outside)
        self.assertEqual({}, space.running())   # every claim released


    def test_a_lane_turn_stamps_every_event_then_releases_the_context(self):
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        book = book_of("T1")
        loop = FakeLoop()

        def record(task):
            space.event("inside", task=task["id"])
            return TaskOutcome("done", "")

        loop.run_task = record
        run_lanes(loop, book, space, book.tasks(), turn_id="turn-7")
        turn_rows = [row for row in space.events() if row["kind"] != "init"]
        self.assertTrue(all(row.get("turn") == "turn-7" for row in turn_rows))
        space.event("outside")
        self.assertNotIn("turn", space.events()[-1])

    def test_a_turn_pauses_only_when_every_lane_points_outside(self):
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        book = book_of("T1", "T2")
        loop = FakeLoop()
        loop.run_task = lambda task: TaskOutcome("waiting" if task["id"] == "T1" else "done", "")
        self.assertFalse(run_lanes(loop, book, space, book.tasks())[1])
        loop.run_task = lambda task: TaskOutcome("waiting", "")
        self.assertTrue(run_lanes(loop, book, space, book.tasks())[1])


class ReachTest(unittest.TestCase):
    def test_two_lanes_never_share_a_path_a_directory_or_a_sibling_slot(self):
        rows = [{"id": "T1", "goal": "g", "status": "todo", "needs": [], "gate": "true", "done_when": "x",
                 "files": ["pkg/a.py"], "may_add_files": True},
                {"id": "T2", "goal": "g", "status": "todo", "needs": [], "gate": "true", "done_when": "x",
                 "files": ["pkg/b.py"]},                      # same directory: T1 may add files there
                {"id": "T3", "goal": "g", "status": "todo", "needs": [], "gate": "true", "done_when": "x",
                 "files": ["other/c.py"]}]
        path = pathlib.Path(tempfile.mkdtemp()) / "b.yaml"
        path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": rows}, sort_keys=False))
        book = Backlog(path)
        self.assertEqual(["T1", "T3"], [row["id"] for row in book.startable()])

    def test_a_directory_grant_holds_everything_beneath_it(self):
        rows = [{"id": "T1", "goal": "g", "status": "todo", "needs": [], "gate": "true", "done_when": "x",
                 "files": ["pkg"]},
                {"id": "T2", "goal": "g", "status": "todo", "needs": [], "gate": "true", "done_when": "x",
                 "files": ["pkg/deep/d.py"]}]
        path = pathlib.Path(tempfile.mkdtemp()) / "b.yaml"
        path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": rows}, sort_keys=False))
        self.assertEqual(["T1"], [row["id"] for row in Backlog(path).startable()])


    def test_two_root_level_cards_that_may_add_files_never_run_together(self):
        rows = [{"id": "T1", "goal": "g", "status": "todo", "needs": [], "gate": "true", "done_when": "x",
                 "files": ["a.py"], "may_add_files": True},
                {"id": "T2", "goal": "g", "status": "todo", "needs": [], "gate": "true", "done_when": "x",
                 "files": ["b.py"], "may_add_files": True}]
        path = pathlib.Path(tempfile.mkdtemp()) / "b.yaml"
        path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": rows}, sort_keys=False))
        self.assertEqual(["T1"], [row["id"] for row in Backlog(path).startable()])


    def test_an_evidence_card_with_no_files_runs_alone(self):
        rows = [{"id": "E1", "goal": "g", "status": "todo", "needs": [], "gate": "true", "done_when": "x", "files": []},
                {"id": "T2", "goal": "g", "status": "todo", "needs": [], "gate": "true", "done_when": "x", "files": ["a.py"]}]
        path = pathlib.Path(tempfile.mkdtemp()) / "b.yaml"
        path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": rows}, sort_keys=False))
        ready = Backlog(path).startable()
        def code_card(row):
            return not runs_alone(row)
        self.assertFalse(code_card(ready[0]))          # the evidence card is not a lane's work
        self.assertEqual(["T2"], [r["id"] for r in ready if code_card(r)])
        # the local duplicate reads the shared predicate, not its own field check
        with unittest.mock.patch("test_lanes.runs_alone", return_value=True):
            self.assertFalse(code_card(ready[1]))       # T2 looks "alone" once the patch says so


    def test_a_lane_that_dies_after_its_keep_does_not_undo_it(self):
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        book = book_of("T1")
        class Loop:
            def run_task(self, task):
                book.set_status("T1", "done", commit="abc")   # the keep happened
                raise RuntimeError("and then the lane died")
        run_lanes(Loop(), book, space, book.tasks())
        self.assertEqual("done", book.task("T1")["status"])   # the branch holds it: it stays done

    def test_one_card_per_id_in_a_turn(self):
        rows = [{"id": "T1", "goal": "g", "status": "todo", "needs": [], "gate": "true", "done_when": "x",
                 "files": ["a.py"]},
                {"id": "T1", "goal": "g", "status": "todo", "needs": [], "gate": "true", "done_when": "x",
                 "files": ["b.py"]}]                          # same id, different files
        path = pathlib.Path(tempfile.mkdtemp()) / "b.yaml"
        path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": rows}, sort_keys=False))
        self.assertEqual(1, len(Backlog(path).startable()))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
