"""Settled is not proof. The coverage prompt says what each status means.

Codex's review: the prompt told the reviewer that every settled molecule was
"finished work whose gate already passed on the branch". `backlog_status.settled`
holds three different things — done, dropped, and a sliced parent whose pieces
are settled — and only the first has a gate that passed. A dropped card's claim
is covered only if some other molecule carries it, and the reviewer was never
shown that card's contract to judge it.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from asking import coverage_prompt

EXPECTED_TESTS = 1

ROWS = [
    {"id": "kept", "status": "done", "goal": "the kept one",
     "done_when": "the kept test passes"},
    {"id": "gone", "status": "dropped", "goal": "the abandoned one",
     "done_when": "THE ABANDONED CONDITION"},
    {"id": "parent", "status": "sliced", "goal": "the replaced one",
     "needs": ["parent.a"], "done_when": "the replaced condition"},
    {"id": "parent.a", "status": "done", "goal": "the piece",
     "done_when": "the piece passes"},
]


class StatusTest(unittest.TestCase):
    def test_a_dropped_card_is_judged_and_never_called_a_passed_gate(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        source = repo / "greeting.md"
        source.write_text("## Goal\nReturn a greeting.\n", "utf-8")

        text = coverage_prompt(repo, [source], ROWS)

        self.assertIn("THE ABANDONED CONDITION", text)   # the dropped card's own contract
        self.assertNotIn("whose gate already passed", text)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
