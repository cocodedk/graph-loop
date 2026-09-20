"""A card a lane is building is not published over.

The slice runs beside the builders now, and outlives the turn that started it:
the card it chose can be requeued and started by a later wave while it plans.
That is not a hold and not a contract edit, so `moved_under` sees nothing — the
claims file is what says a builder has it. The rig is `test_tree_card_moved`'s.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
DRIVE_LIB = HERE.parent / "drive" / "lib"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(DRIVE_LIB))
import intelligence
from backlog import Backlog  # type: ignore[import-not-found]
from test_tree import task
from tree import CardMoved, publish
from workspace import Workspace  # type: ignore[import-not-found]

EXPECTED_TESTS = 1


class CardRunningTest(unittest.TestCase):
    def test_a_card_a_lane_is_building_is_not_published_over(self):
        root = pathlib.Path(tempfile.mkdtemp())
        backlog = root / "backlog"
        backlog.mkdir()
        book = Backlog(backlog)
        publish(backlog, task("large"))
        book.set_status("large", "needs_slice", refused_why="too broad")
        started = book.task("large")
        space = Workspace(root / "campaign").init(goal="g", backlog=str(backlog))
        space.claim("large", pid=os.getpid(), pgid=os.getpgid(0),
                    account="lane", worktree="")
        was, intelligence.CAMPAIGN = intelligence.CAMPAIGN, space.root
        try:
            with self.assertRaises(CardMoved):
                publish(backlog, task("small"), "large", started)
        finally:
            intelligence.CAMPAIGN = was
        row = book.task("large")
        self.assertEqual("needs_slice", row["status"])   # not settled under its builder
        self.assertNotIn("small", row.get("needs") or [])


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
