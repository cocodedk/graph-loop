"""Recovery asks the same question the planned publish asks.

`roll_forward` finishes an interrupted publish: the child folder is on disk and
only the parent's own settling is missing. It settles the card, so it is a
publish, and a lane may be building that card right now — the campaign has to
be known before recovery runs, not after it.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parents[1]
DRIVE_LIB = HERE.parent / "drive" / "lib"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(DRIVE_LIB))
import intelligence
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog  # type: ignore[import-not-found]
from test_tree import task
from tree import publish
from workspace import Workspace  # type: ignore[import-not-found]

import slicer

EXPECTED_TESTS = 1


class RecoveryRunningTest(unittest.TestCase):
    def test_recovery_does_not_settle_a_card_a_lane_is_building(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        backlog, specs = repo / "backlog", repo / "specs"
        backlog.mkdir(); specs.mkdir()
        (specs / "greeting.md").write_text("## Goal\nReturn a greeting.\n", "utf-8")
        book = Backlog(backlog)
        publish(backlog, task("large"))
        publish(backlog, task("small"), "large")      # the child landed...
        book.set_status("large", "needs_slice", needs=[], triage="work",
                        refused_why="too broad")      # ...and the parent's write did not
        space = Workspace(repo / "campaign").init(goal="g", backlog=str(backlog))
        space.claim("large", pid=os.getpid(), pgid=os.getpgid(0),
                    account="lane", worktree="")
        was = intelligence.CAMPAIGN
        try:
            with mock.patch.object(slicer, "ask") as ask:
                result = slicer.main(["--repo", str(repo), "--backlog", str(backlog),
                                      "--campaign", str(space.root), "--target", "large",
                                      "--source", "specs/greeting.md"])
        finally:
            intelligence.CAMPAIGN = was
        ask.assert_not_called()          # no model call either way
        self.assertEqual(2, result)      # uncharged: `card_moved` is in UNANSWERED
        self.assertEqual("needs_slice", book.task("large")["status"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
