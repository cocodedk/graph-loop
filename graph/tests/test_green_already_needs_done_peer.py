"""A green gate alone cannot name any work as already delivered."""

from __future__ import annotations

import pathlib
import unittest

from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 2


class GreenAlreadyTest(unittest.TestCase):
    def test_a_first_round_with_unique_files_and_no_done_peer_parks(self):
        for peers in ([], [task(id="T0", status="done", files=["other.py"])]):
            with self.subTest(peers=peers):
                fakes = Fakes()
                loop, book, _ = loop_for(task(gate="true"), fakes, peers)
                out = loop.run_task(book.task("T1"))
                self.assertEqual("refused", out.state)
                self.assertEqual("green_already", book.task("T1")["status"])
                self.assertNotIn("done_why", book.task("T1"))
                self.assertTrue(pathlib.Path(out.worktree).is_dir())
                self.assertEqual([], fakes.calls)

    def test_a_dropped_same_file_peer_is_not_delivered_work(self):
        fakes = Fakes()
        loop, book, _ = loop_for(task(gate="true"), fakes,
                                [task(id="T0", status="dropped")])
        out = loop.run_task(book.task("T1"))
        self.assertEqual("refused", out.state)
        self.assertEqual("green_already", book.task("T1")["status"])
        self.assertNotIn("done_why", book.task("T1"))
        self.assertTrue(pathlib.Path(out.worktree).is_dir())
        self.assertEqual([], fakes.calls)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        self.assertEqual(EXPECTED_TESTS + 1,
                         unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases())


if __name__ == "__main__":
    unittest.main()
