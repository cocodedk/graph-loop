"""A campaign still holding work nobody can take ends with its gaps, never zero.

Zero tells `supervisor.sh` the backlog is worked out and it stands down for
good. A card left `rejected`, with no decider available to resolve it, is
nothing startable and nothing dropped — so `stand_down` walked past the dropped
check and said the campaign was finished (astra's round-4 finding 12). Work
that was never proved is a gap whatever status it stopped in, and the receipt
`end_with_gaps` already writes is what says so.

Companion to test_dropped_work_is_not_a_finish.py, which covers the drops.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import source_gap
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from campaigns import campaign
from finishing import ENDED_WITH_GAPS, stand_down

EXPECTED_TESTS = 1
DONE = {"id": "T1", "status": "done", "goal": "read the journal", "files": ["a.py"],
        "gate": "true", "needs": []}
LEFT = {"id": "T2", "status": "rejected", "goal": "prove the broker replays",
        "files": ["b.py"], "gate": "true", "needs": [],
        "refused_why": "the diff does not prove the replay"}


class UnfinishedWorkTest(unittest.TestCase):
    def test_a_card_nobody_resolved_ends_the_campaign_with_its_gap(self):
        book, space = campaign([dict(DONE), dict(LEFT)])

        self.assertEqual(ENDED_WITH_GAPS, stand_down(space, book))
        gaps = source_gap.ended(space)
        assert gaps is not None
        self.assertIn("T2", gaps["gaps"])
        self.assertIn("does not prove the replay", gaps["gaps"])
        self.assertEqual(["T2"], gaps["left"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
