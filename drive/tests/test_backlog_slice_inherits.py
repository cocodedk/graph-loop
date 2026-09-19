"""A slice keeps what its parent declared about how it is judged.

`_slice` built each piece from the piece alone, so a parent's
`gate_files_are_the_work` was dropped. The loop refuses a card whose gate runs a
test in its own files unless that flag is set, at the scope check, before a
builder is paid for — so slicing a card like that produced pieces that could
never start.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from backlog import Backlog

EXPECTED_TESTS = 6


def book(parent: dict) -> Backlog:
    path = pathlib.Path(tempfile.mkdtemp()) / "backlog.yaml"
    path.write_text(yaml.safe_dump({"tasks": [parent]}))
    return Backlog(path)


PARENT = {"id": "T4", "status": "todo", "needs": [], "files": ["a_test.py"],
          "gate": "python3 -m unittest a_test", "gate_files_are_the_work": True,
          "gate_has_side_effects": True, "helper_verbs": ["journal"]}
PIECE = {"goal": "one idea", "files": ["b_test.py"], "gate": "python3 -m unittest b_test",
         "done_when": "it holds"}


class ASliceKeepsItsParentsTerms(unittest.TestCase):
    def test_the_test_is_the_work_flag_is_carried(self):
        rows = book(dict(PARENT))
        rows.slice_task("T4", [dict(PIECE)])
        self.assertTrue(rows.task("T4.1")["gate_files_are_the_work"])

    def test_a_live_parent_makes_live_pieces_with_its_verbs(self):
        rows = book(dict(PARENT))
        rows.slice_task("T4", [dict(PIECE)])
        piece = rows.task("T4.1")
        self.assertTrue(piece["gate_has_side_effects"])
        self.assertEqual(["journal"], piece["helper_verbs"])

    def test_a_piece_that_says_otherwise_wins(self):
        rows = book(dict(PARENT))
        rows.slice_task("T4", [dict(PIECE, gate_files_are_the_work=False)])
        self.assertFalse(rows.task("T4.1")["gate_files_are_the_work"])

    def test_a_hold_on_the_parent_does_not_strand_the_pieces(self):
        """A hold is a decision about the parent at a moment; inheriting it made
        every new piece unstartable the instant it was written."""
        rows = book(dict(PARENT, blocked_by_human=True))
        rows.slice_task("T4", [dict(PIECE)])
        self.assertFalse(rows.task("T4.1").get("blocked_by_human"))

    def test_the_parents_red_first_phrase_is_not_carried(self):
        """expect_red names what the PARENT's gate prints; a piece has its own."""
        rows = book(dict(PARENT, expect_red="the parent's own words"))
        rows.slice_task("T4", [dict(PIECE)])
        self.assertNotIn("expect_red", rows.task("T4.1"))

    def test_a_parent_that_declared_nothing_adds_nothing(self):
        plain = {"id": "T4", "status": "todo", "needs": [], "files": ["a.py"], "gate": "true"}
        rows = book(plain)
        rows.slice_task("T4", [dict(PIECE)])
        self.assertNotIn("gate_files_are_the_work", rows.task("T4.1"))


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
