"""A campaign that recorded no init event planned into the driver's own directory.

`Workspace.init` asked whether `events.jsonl` EXISTED, not whether an init event
was in it. Any other command writing first — `approve`, in the case that found
this — creates that file, so `init` wrote nothing and still printed the backlog
it had been handed, which reads as confirmation that it recorded exactly that.

`campaign_of.backlog_of` then answers `""`, and `pathlib.Path("")` is the current
directory. A whole plan phase landed in the repository root: seven molecules, a
trace and a lock, every one reported as published, with no warning anywhere and a
`status` that would have shown an empty backlog (2026-09-18).

Three guards, because the failure needed all three to be silent: the event is
recorded whatever wrote first, no backlog is refused rather than resolved to
wherever the process stands, and `init` reports what the campaign HOLDS instead
of what the call asked for.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from campaign_of import backlog_of
from workspace import Workspace

EXPECTED_TESTS = 5


class TheInitEventIsRecordedWhateverWroteFirst(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.space = Workspace(str(self.root / "campaign"))

    def test_init_first_records_the_backlog(self):
        self.space.init(goal="g", backlog=str(self.vault))
        self.assertEqual(str(self.vault), backlog_of(self.space))

    def test_another_command_writing_first_does_not_swallow_it(self):
        # `approve` writes an event, which used to create the file the guard read
        self.space.event("approved")
        self.space.init(goal="g", backlog=str(self.vault))
        self.assertEqual(str(self.vault), backlog_of(self.space))

    def test_a_second_init_does_not_move_a_running_campaign(self):
        self.space.init(goal="g", backlog=str(self.vault))
        other = self.root / "elsewhere"
        other.mkdir()
        self.space.init(goal="g", backlog=str(other))
        self.assertEqual(str(self.vault), backlog_of(self.space))
        self.assertEqual(1, sum(1 for row in self.space.events() if row.get("kind") == "init"))


class NoBacklogIsNeverThisDirectory(unittest.TestCase):
    def test_an_unstarted_campaign_still_answers_nothing(self):
        space = Workspace(str(pathlib.Path(tempfile.mkdtemp()) / "fresh"))
        self.assertEqual("", backlog_of(space))

    def test_the_empty_path_is_refused_rather_than_resolved(self):
        # the whole defect in one line: `Backlog("")` used to be the cwd
        with self.assertRaises(ValueError) as refused:
            Backlog(backlog_of(Workspace(str(pathlib.Path(tempfile.mkdtemp()) / "fresh"))))
        self.assertIn("no init event", str(refused.exception))


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
