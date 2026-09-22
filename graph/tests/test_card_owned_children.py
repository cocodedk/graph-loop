"""Detached descendants end with their card; unrelated children remain alive."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import runner
from lanes import run_lanes
from loop_types import TaskOutcome
from test_loop import Fakes, loop_for, task

# Double detachment escapes a process group, and closed pipes let the leader
# return. The marker proves the descendant really started before that return.
DETACH = '''
import os, pathlib, signal, sys, time
marker = pathlib.Path(sys.argv[1])
if os.fork() == 0:
    os.setsid()
    if os.fork() != 0:
        os._exit(0)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    for fd in (0, 1, 2):
        os.close(fd)
    marker.write_text(str(os.getpid()))
    time.sleep(30)
    os._exit(0)
while not marker.exists():
    time.sleep(0.01)
if sys.argv[2] == 'wait':
    time.sleep(30)
'''


class ChildrenTest(unittest.TestCase):
    def test_success_and_timeout_reap_detached_children(self):
        for ending in ("success", "wait"):
            with self.subTest(ending=ending), tempfile.TemporaryDirectory() as directory:
                marker = pathlib.Path(directory) / "child"
                loop, book, space = loop_for(task(), Fakes())
                result = []

                def run(_card, result=result, marker=marker, ending=ending):
                    try:
                        result.append(runner.run([sys.executable, "-c", DETACH,
                                                  str(marker), ending], timeout=2))
                    except subprocess.TimeoutExpired:
                        result.append("timeout")
                    return TaskOutcome("done", "")

                loop.run_task = run
                with patch("lane_closing.capacity", return_value=""):
                    run_lanes(loop, book, space, book.tasks())
                self.assertTrue(marker.exists())
                self.assertFalse(pathlib.Path(f"/proc/{marker.read_text()}").exists())
                self.assertEqual("timeout" if ending == "wait" else 0,
                                 result[0] if ending == "wait" else result[0].returncode)

    def test_one_lane_closes_without_signalling_its_sibling(self):
        loop, book, space = loop_for(task(), Fakes())
        ready, closed = threading.Event(), threading.Event()
        results = []
        second = task(id="T2", files=["b.py"])
        # Supply a second real card so claims and status writes use the same path.
        from test_loop import repo_with
        root, book, space = repo_with(task(), [second])
        loop.repo = root

        def run(card):
            if card["id"] == "T1":
                ready.set()
                results.append(runner.run([sys.executable, "-c", "import time; time.sleep(1)"],
                                          timeout=10).returncode)
                closed.set()
            else:
                ready.wait(5)
                results.append(runner.run([sys.executable, "-c", "print('still here')"],
                                          timeout=10).returncode)
            return TaskOutcome("done", "")

        loop.run_task = run
        with patch("lane_closing.capacity", return_value=""):
            run_lanes(loop, book, space, book.tasks())
        self.assertTrue(closed.is_set())
        self.assertEqual([0, 0], results)

    def test_unrelated_process_is_not_a_cleanup_target(self):
        # The test itself owns this sentinel; the card must never signal it.
        sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            loop, book, space = loop_for(task(), Fakes())
            loop.run_task = lambda _card: (
                runner.run([sys.executable, "-c", "print('done')"], timeout=10)
                and TaskOutcome("done", ""))
            with patch("lane_closing.capacity", return_value=""):
                run_lanes(loop, book, space, book.tasks())
            self.assertIsNone(sentinel.poll())
        finally:
            sentinel.terminate()
            sentinel.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
