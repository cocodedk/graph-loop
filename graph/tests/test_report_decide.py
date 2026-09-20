"""Decider spend, told apart from build spend and from "we don't know".

A decision call is told apart only by `purpose="decide"` (workspace.py
`attempt`), the same way a review is. Codex reports no figure at all, so a
decide call with no cost is counted as unknown and never folded into the known
total as a silent zero — a call read as free makes the campaign's spend a lie.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from report import as_text, report
from workspace import Workspace

EXPECTED_TESTS = 1


class DecideSpendTest(unittest.TestCase):
    def test_known_and_unknown_decider_spend_are_told_apart(self):
        here = Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog="b.yaml")
        here.attempt("T1", account="work", kind="ok", cost=9.0)    # a build
        here.attempt("T1", account="second", kind="ok", cost=0.40, purpose="review")
        here.attempt("T1", account="second", kind="ok", cost=1.25, purpose="decide")
        here.attempt("T2", account="second", kind="ok", purpose="decide")   # codex: no figure
        out = report(here)
        self.assertAlmostEqual(1.25, out["decide_spend_known"])
        self.assertEqual(1, out["decide_calls_unknown_cost"])
        text = as_text(out)
        self.assertIn("decisions: $1.25 known, 1 call with no figure", text)
        self.assertIn("reviews: $0.40 known", text)      # still its own line


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
