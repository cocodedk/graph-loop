"""TRIAGE catches up from durable lane boundaries without losing an ending."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from triage_evidence import MAX_ARTIFACT_BYTES, pending_endings
from workspace import Workspace

EXPECTED_TESTS = 7
STAMP = "2026-09-01T12:00:00Z"


class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        path = self.root / "backlog.yaml"
        path.write_text(yaml.safe_dump({"tasks": [
            {"id": "T1", "status": "todo", "files": ["a.py"]},
            {"id": "T2", "status": "todo", "files": ["b.py"]}]}))
        self.book = Backlog(path)
        self.space = Workspace(self.root / "campaign")

    def test_release_closes_one_lane_without_leaking_another(self):
        self.space.event("claimed", task="T1")
        self.space.event("claimed", task="T2")
        self.space.artifact("T1", "gate-output", "one")
        self.space.event("failed", task="T2", step="gate", why="not T1")
        self.space.event("failed", task="T1", step="gate", why="one")
        self.space.event("released", task="T1", turn="turn-7")
        [found] = pending_endings(self.book, self.space)
        self.assertEqual("T1", found.task)
        self.assertEqual(("one",), found.artifacts["gate-output"])
        self.assertNotIn("T2", {row.get("task") for row in found.events})
        self.assertEqual("released", found.closed_kind)

    def test_the_next_claim_closes_a_lane_whose_release_failed(self):
        self.space.event("claimed", task="T1")
        self.space.event("review_unavailable", task="T1", step="diff_review")
        self.space.event("rebuild_queued", task="T1", round=1)
        closing = self.space.event("claimed", task="T1")
        [found] = pending_endings(self.book, self.space)
        self.assertEqual("claimed", found.closed_kind)
        self.assertEqual(closing["at"], found.closed_at)
        self.assertEqual(("review_unavailable", "rebuild_queued"),
                         tuple(row["kind"] for row in found.events[1:]))

    def test_an_empty_boundary_is_returned_once_to_advance_its_cursor(self):
        self.space.event("claimed", task="T1")
        self.space.event("worktree", task="T1")
        self.space.event("released", task="T1")
        [found] = pending_endings(self.book, self.space)
        self.space.event("triage", task="T1", verdict=None,
                         closed_at=found.closed_at, closed_index=found.closed_index,
                         closed_kind=found.closed_kind)
        self.assertEqual([], pending_endings(self.book, self.space))

    @mock.patch("workspace._now", return_value=STAMP)
    def test_full_log_index_orders_two_endings_in_the_same_second(self, _now):
        self.space.event("claimed", task="T1")
        self.space.event("failed", task="T1", step="gate")
        self.space.event("released", task="T1")
        self.space.event("quarantined", task="T1", why="spin")
        first, second = pending_endings(self.book, self.space)
        self.assertEqual(first.closed_at, second.closed_at)
        self.space.event("triage", task="T1", verdict="work",
                         closed_at=first.closed_at, closed_index=first.closed_index,
                         closed_kind=first.closed_kind)
        [left] = pending_endings(self.book, self.space)
        self.assertEqual(second.closed_index, left.closed_index)
        self.space.event("triage", task="T1", verdict="work",
                         closed_at=left.closed_at, closed_index=left.closed_index,
                         closed_kind=left.closed_kind)
        self.assertEqual([], pending_endings(self.book, self.space))

    @mock.patch("workspace._now", return_value=STAMP)
    def test_a_stale_index_replays_equal_time_instead_of_losing_it(self, _now):
        self.space.event("claimed", task="T1")
        self.space.event("accepted", task="T1")
        self.space.event("released", task="T1")
        closed = pending_endings(self.book, self.space)[0]
        self.space.event("triage", task="T1", verdict=None, closed_at=closed.closed_at,
                         closed_index=0, closed_kind=closed.closed_kind)
        self.assertEqual([closed.closed_index],
                         [row.closed_index for row in pending_endings(self.book, self.space)])

    def test_artifact_reads_are_bounded_and_symlink_loops_are_ignored(self):
        large = self.space.root / "large.txt"
        large.write_text("x" * (MAX_ARTIFACT_BYTES + 50))
        loop = self.space.root / "loop"
        loop.symlink_to(loop.name)
        self.space.event("claimed", task="T1")
        self.space.event("artifact", task="T1", name="diff", path=str(large))
        self.space.event("artifact", task="T1", name="answer", path=str(loop))
        self.space.event("failed", task="T1", step="gate")
        self.space.event("released", task="T1")
        [found] = pending_endings(self.book, self.space)
        self.assertEqual(MAX_ARTIFACT_BYTES, len(found.artifacts["diff"][0]))
        self.assertNotIn("answer", found.artifacts)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
