"""The queue that had work in it and could not start any of it.

On 2026-08-30 the loop sat idle for half an hour with fifteen todo cards, a live
driver and a green `--check`. Every card waited on one the loop had handed back.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from doctor_starved import check_starved

EXPECTED_TESTS = 7


def card(task_id: str, status: str = "todo", needs: list[str] | None = None, **extra) -> dict:
    return {"id": task_id, "status": status, "needs": needs or [], **extra}


class Starved(unittest.TestCase):
    def test_todo_cards_that_all_wait_on_a_handed_back_card_are_a_complaint(self):
        tasks = [card("T4", needs=["T26"]), card("T5", needs=["T4"]),
                 card("T26", status="rejected")]
        [complaint] = check_starved(tasks, claimed=0)
        self.assertIn("none can start", complaint.what)
        self.assertIn("T26", complaint.what)

    def test_one_ready_card_is_not_starvation(self):
        tasks = [card("T4", needs=["T26"]), card("T9"), card("T26", status="rejected")]
        self.assertEqual(check_starved(tasks, claimed=0), [])

    def test_a_claimed_lane_is_not_starvation(self):
        tasks = [card("T4", needs=["T26"]), card("T26", status="rejected")]
        self.assertEqual(check_starved(tasks, claimed=1), [])

    def test_an_empty_queue_is_not_starvation(self):
        self.assertEqual(check_starved([card("T1", status="done")], claimed=0), [])

    def test_a_card_held_for_a_person_is_not_counted_as_starved(self):
        tasks = [card("T4", needs=["T26"], blocked_by_human=True), card("T26", status="rejected")]
        self.assertEqual(check_starved(tasks, claimed=0), [])


class TheBoardNeverWaits(unittest.TestCase):
    def test_diagnose_answers_while_a_keep_holds_the_backlog_lock(self):
        """The board used to wait behind a keep: it holds the backlog lock
        across a combined-tree gate (loop_judge.py passes
        `backlog.only_writer` as its publishing lock), and every check the
        doctor ran read through that lock."""
        import tempfile
        import threading

        import yaml  # type: ignore[import-untyped]  # no stubs in this environment
        from backlog import Backlog
        from doctor import diagnose
        from workspace import Workspace
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "backlog.yaml").write_text(yaml.safe_dump({"tasks": [card("T1")]}))
            book, space = Backlog(root / "backlog.yaml"), Workspace(root)
            holding, release = threading.Event(), threading.Event()

            def keeping():
                with book.only_writer():        # the lock a keep holds across its gate
                    holding.set()
                    release.wait(5)

            hand = threading.Thread(target=keeping)
            hand.start()
            self.assertTrue(holding.wait(5))
            answered = threading.Event()
            threading.Thread(target=lambda: (diagnose(book, space, []), answered.set())).start()
            self.assertTrue(answered.wait(2), "the doctor waited for the keep's lock")
            release.set()
            hand.join(5)


class DeadClaimsAreNotBusyLanes(unittest.TestCase):
    def test_a_claim_whose_process_is_gone_does_not_hide_a_starved_queue(self):
        """`running` prunes dead claims; the lock-free read must judge them the
        same way, or one abandoned claim silences the starvation warning."""
        import json
        import tempfile

        import yaml  # type: ignore[import-untyped]  # no stubs in this environment
        from backlog import Backlog
        from doctor import diagnose
        from workspace import Workspace
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "backlog.yaml").write_text(yaml.safe_dump({"tasks": [
                card("T4", needs=["T26"]), card("T26", status="rejected")]}))
            (root / "claims.json").write_text(json.dumps(
                {"T4": {"pid": 2 ** 22, "pgid": 2 ** 22, "started": "0", "account": "x",
                        "worktree": str(root)}}))          # a pid that cannot exist
            book, space = Backlog(root / "backlog.yaml"), Workspace(root)
            self.assertEqual(space.claimed_now(), {}, "a dead claim read as a live lane")
            starved = [c for c in diagnose(book, space, []) if c.about == "the queue"]
            self.assertTrue(starved, "the dead claim hid the starved queue")


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
