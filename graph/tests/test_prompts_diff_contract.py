"""The diff reviewer reads the same contract the contract reviewer accepted.

2026-09-03, card `ip-investigator-one-recommendation.recommendation-rule-test`:
the diff review asked for a `run_all.py` the card's note forbade by name, the
builder refused in writing and a person had to settle it. The prompt showed the
goal, the done-when and the file list — never the note, the gate or the live
helper verbs — so the reviewer judged a change against a wider contract than
the one that was accepted.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from prompts import contract_digest, diff_prompt

EXPECTED_TESTS = 1

CARD = {
    "id": "T1",
    "goal": "one rule test for the recommendation",
    "files": ["rules/recommendation.py"],
    "gate": "python3 -m unittest tests.test_recommendation_rule",
    "done_when": "the rule test fails on the old rule",
    "note": "no run_all.py anywhere, the gate runs the one file",
    "gate_has_side_effects": True,
    "helper_verbs": ["sc seed-suspect-ip"],
    "rejections": ["round one left the old rule in place"],
}


class DiffContractTest(unittest.TestCase):
    def test_the_diff_reviewer_is_shown_the_whole_accepted_contract(self):
        prompt = diff_prompt(CARD, "diff")
        self.assertIn(CARD["note"], prompt)                 # the exclusion
        self.assertIn(CARD["gate"], prompt)                 # what actually judges it
        self.assertIn("sc seed-suspect-ip", prompt)         # the authority it was granted
        self.assertIn(CARD["rejections"][0], prompt)        # the previous round's reasons
        self.assertIn(contract_digest(CARD), prompt)        # which contract that was


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
