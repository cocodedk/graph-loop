"""A sibling molecule's link survives a write; an in-folder atom's is derived."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog

EXPECTED_TESTS = 1


class ChildLinkTest(unittest.TestCase):
    def test_a_link_to_a_sibling_molecule_survives_a_status_write(self):
        root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
        (root / "T6").mkdir(parents=True)
        (root / "T6" / "molecule.md").write_text(cardfile.dump(
            {"status": "sliced", "goal": "parent", "needs": ["T2", "T6.approver"]}))
        (root / "T6" / "01-inner.md").write_text(cardfile.dump(
            {"status": "todo", "goal": "atom", "files": ["a.py"], "gate": "false",
             "done_when": "p"}))
        (root / "T6.approver").mkdir()
        (root / "T6.approver" / "molecule.md").write_text(cardfile.dump(
            {"status": "todo", "goal": "the piece", "files": ["b.py"], "gate": "false",
             "done_when": "p"}))
        book = Backlog(root)
        book.set_status("T6", "sliced")
        after = {row["id"]: row for row in Backlog(root).tasks()}["T6"]
        self.assertIn("T6.approver", after["needs"])     # the sibling link is not derived
        self.assertIn("T6.inner", after["needs"])        # the atom's is, from its file


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
