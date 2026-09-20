"""The backlog picker: what may start, what waits, what a slice does.

Written before the loop that uses it. Every case builds its own small backlog file
in a temporary directory, so nothing here reads the real campaign.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog

EXPECTED_TESTS = 15


def write(tasks: list[dict]) -> Backlog:
    path = pathlib.Path(tempfile.mkdtemp()) / "backlog.yaml"
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": tasks}, handle,
                       sort_keys=False)
    return Backlog(path)


def task(task_id, status="todo", needs=None, files=None, **extra):
    row = {"id": task_id, "goal": f"do {task_id}", "status": status,
           "needs": needs or [], "files": files or [], "gate": "true",
           "done_when": "it is done"}
    row.update(extra)
    return row


class ReadyTest(unittest.TestCase):
    def test_a_task_with_no_dependencies_is_ready(self):
        book = write([task("T1")])
        self.assertEqual(["T1"], [row["id"] for row in book.ready()])

    def test_a_task_waits_for_every_one_of_its_needs(self):
        book = write([task("T1", status="done"), task("T2", needs=["T1", "T3"]),
                      task("T3")])
        self.assertEqual(["T3"], [row["id"] for row in book.ready()])

    def test_a_task_that_is_not_todo_is_never_ready(self):
        book = write([task("T1", status="doing"), task("T2", status="done")])
        self.assertEqual([], book.ready())

    def test_a_held_task_is_ready_but_never_startable(self):
        book = write([task("T1", blocked_by_human=True), task("T2")])
        self.assertEqual(["T1", "T2"], [row["id"] for row in book.ready()])
        self.assertEqual(["T2"], [row["id"] for row in book.startable()])
        self.assertEqual(["T1"], [row["id"] for row in book.waiting_for_human()])


class ScopeTest(unittest.TestCase):
    def test_two_tasks_that_share_a_file_never_start_together(self):
        book = write([task("T1", files=["a.py"]), task("T2", files=["a.py", "b.py"]),
                      task("T3", files=["c.py"])])
        self.assertEqual(["T1", "T3"], [row["id"] for row in book.startable()])

    def test_a_running_task_holds_its_files_against_the_next_pick(self):
        book = write([task("T1", status="doing", files=["a.py"]),
                      task("T2", files=["a.py"]), task("T3", files=["d.py"])])
        self.assertEqual(["T3"],
                         [row["id"] for row in book.startable(running=["T1"])])

    def test_a_task_with_no_files_is_evidence_and_one_with_files_is_code(self):
        book = write([task("T1"), task("T2", files=["a.py"])])
        self.assertEqual(["evidence", "code"],
                         [book.kind(row) for row in book.tasks()])


class SliceTest(unittest.TestCase):
    def test_a_slice_keeps_the_parent_as_the_thing_downstream_waits_for(self):
        book = write([task("T1", needs=["T0"]), task("T0", status="done"),
                      task("T2", needs=["T1"])])
        ids = book.slice_task("T1", [{"goal": "first half", "files": ["a.py"]},
                                     {"goal": "second half", "files": ["b.py"]}])
        self.assertEqual(["T1.1", "T1.2"], ids)
        parent = book.task("T1")
        self.assertEqual("sliced", parent["status"])
        self.assertEqual(["T0", "T1.1", "T1.2"], parent["needs"])
        # The pieces inherit the parent's own dependency, so they cannot start
        # before what the parent was waiting for.
        self.assertEqual(["T0"], book.task("T1.1")["needs"])
        self.assertEqual(["T1.1", "T1.2"], [r["id"] for r in book.ready()])
        # And T2, which waited for T1, still waits: T1 is not done.
        self.assertNotIn("T2", [r["id"] for r in book.ready()])

    def test_a_slice_with_no_pieces_is_refused(self):
        book = write([task("T1")])
        with self.assertRaises(ValueError):
            book.slice_task("T1", [])

    def test_status_is_written_back_with_its_evidence(self):
        book = write([task("T1")])
        book.set_status("T1", "done", commit="abc1234")
        self.assertEqual(("done", "abc1234"),
                         (book.task("T1")["status"], book.task("T1")["commit"]))
        self.assertEqual([], book.unfinished())


class NoteTest(unittest.TestCase):
    def test_note_writes_fields_without_touching_status(self):
        book = write([task("T1", status="live_call_open", stale="x")])
        row = book.note("T1", session="sess-1", stale=None)
        self.assertEqual("live_call_open", row["status"])   # status untouched
        self.assertEqual("sess-1", row["session"])            # field written
        self.assertNotIn("stale", row)                        # None pops the key
        self.assertEqual(("live_call_open", "sess-1"),
                         (book.task("T1")["status"], book.task("T1")["session"]))
        self.assertNotIn("stale", book.task("T1"))


class RequeueTest(unittest.TestCase):
    def test_todo_clears_a_stale_hold_but_other_statuses_keep_it(self):
        # A person's requeue calls set_status(id, "todo") with no opinion on the
        # hold, so the default clears it. A card parked at another status keeps
        # whatever the park call wrote — nobody requeues by leaving status alone.
        book = write([task("T1", status="held", blocked_by_human=True),
                      task("T2", status="held", blocked_by_human=True)])
        book.set_status("T1", "todo")
        self.assertNotIn("blocked_by_human", book.task("T1"))
        self.assertIn("T1", [row["id"] for row in book.startable()])
        book.set_status("T2", "refused_contract")
        self.assertTrue(book.task("T2")["blocked_by_human"])


class ReentrantLockTest(unittest.TestCase):
    def test_the_lock_can_be_taken_twice_in_one_thread(self):
        # The publish path holds it while its gate list and status write read
        # through it; a second acquire must not wait for this thread's own lock.
        book = write([task("T1")])
        # the publish path holds it, and its callbacks take it again
        with book.only_writer(), book.only_writer():
            book.set_status("T1", "todo", note="still moving")
        self.assertEqual("still moving", book.task("T1")["note"])

    def test_two_threads_still_take_turns(self):
        import threading
        import time
        book = write([task("T1")])
        order = []
        def lane(name, wait):
            with book.only_writer():
                order.append(f"{name}-in"); time.sleep(wait); order.append(f"{name}-out")
        first = threading.Thread(target=lane, args=("a", 0.2))
        second = threading.Thread(target=lane, args=("b", 0.0))
        first.start(); time.sleep(0.05); second.start()
        first.join(); second.join()
        self.assertEqual(["a-in", "a-out", "b-in", "b-out"], order)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        loader = unittest.TestLoader()
        found = loader.discover(str(pathlib.Path(__file__).parent),
                                pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
