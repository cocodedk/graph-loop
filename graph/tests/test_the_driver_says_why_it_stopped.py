"""In six campaigns the driver never finished one without a person restarting it,
and the record could not say why, because it did not hold the answer.

`driver_started` was written and nothing was written at the other end. A campaign
that stopped by itself left a log whose last word was that a driver had begun.

One cause is now named and fixed. `code_is_newer` compared every loop file's
MTIME against the driver's start time, and a `git checkout` rewrites the mtime of
every file its commit touches whether or not the bytes changed — so a campaign
run while the loop is being fixed stands its driver down between tasks for code
that is byte for byte what it was already running. It then exits 75, which asks a
supervisor for a fresh driver; a person running `graph-goal.py run` by hand is not
running one, so it reads as a stop (2026-09-18). Hashing what is loaded answers
the question that was always meant.

Naming a cause is not the same as naming every cause, so the record is the fix
that matters: every way out of the driver's loop now says which one it was.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from turn import stood_down
from workspace import Workspace
from workspace_flags import RESTART_EXIT

EXPECTED_TESTS = 6


def space() -> Workspace:
    return Workspace(str(pathlib.Path(tempfile.mkdtemp()) / "campaign"))


class TheRecordSaysWhyItEnded(unittest.TestCase):
    def test_the_reason_and_the_exit_are_both_written(self):
        here = space()
        self.assertEqual(0, stood_down(here, 0, "a person asked it to stop"))
        row = next(one for one in here.events() if one.get("kind") == "driver_stood_down")
        self.assertEqual("a person asked it to stop", row["why"])
        self.assertEqual(0, row["exit"])

    def test_it_says_when_a_supervisor_is_expected_to_start_another(self):
        # exit 75 is a request for a fresh driver, and from outside it looks
        # exactly like a stop — which is how six campaigns read as "it stopped"
        here = space()
        self.assertEqual(RESTART_EXIT, stood_down(here, RESTART_EXIT, "the code changed"))
        row = next(one for one in here.events() if one.get("kind") == "driver_stood_down")
        self.assertTrue(row["supervisor_restarts"])

    def test_a_plain_ending_does_not_claim_a_supervisor_will_act(self):
        here = space()
        stood_down(here, 0, "nothing startable")
        row = next(one for one in here.events() if one.get("kind") == "driver_stood_down")
        self.assertFalse(row["supervisor_restarts"])


class TheCodeCheckReadsTheCode(unittest.TestCase):
    def setUp(self):
        self.space = space()

    def test_the_same_code_is_not_a_change(self):
        digest = self.space.code_digest()
        self.assertFalse(self.space.code_changed(digest))

    def test_a_touched_file_is_not_a_change(self):
        """The whole defect: `git checkout` rewrites mtimes, and the driver stood
        down for bytes that never moved."""
        digest = self.space.code_digest()
        here = pathlib.Path(sys.modules["workspace_flags"].__file__)
        here.touch()
        self.assertFalse(self.space.code_changed(digest))

    def test_a_driver_that_recorded_no_digest_never_restarts_for_it(self):
        # a dry run and an older campaign both reach here with nothing to compare
        self.assertFalse(self.space.code_changed(""))


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
