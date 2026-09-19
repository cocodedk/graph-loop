"""A rewrite is checked against the waits the TREE would give the card back.

`check_rewrite` read the submitted `needs` and nothing else, so `M.b.needs: []`
passed every check while the tree restored `M.b → M.a → X → M.b` on the next
read: the stage numbers derive an atom's waits and the molecule hands down its
own, and neither is written in the atom's file for a rewrite to edit (astra
round 4, finding 4).

The tree is asked here rather than guessed from the id or from `sliced_from`:
an atom cut from another atom sits in the folder and says neither
(`backlog_tree._outside`).
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from campaigns import CODE
from rewrite_guard import check_rewrite

EXPECTED_TESTS = 6
# M.b runs behind M.a, M.a inherits the molecule's wait on X, and X waits for
# M.b: the circle the tree restores the moment M.b's file drops its needs.
MOLECULES = {
    "M": {"molecule.md": {"goal": "the piece", "status": "sliced", "needs": ["X"]},
          "01-a.md": {"goal": "first", "status": "todo", **CODE},
          "02-b.md": {"goal": "second", "status": "rejected", **CODE}},
    "X": {"molecule.md": {"goal": "elsewhere", "status": "todo", "needs": ["M.b"]}},
}
# The same molecule with nothing waiting on it: the other half of the check,
# so a validator that refuses everything is not mistaken for one that works.
STRAIGHT = {**MOLECULES, "X": {"molecule.md": {"goal": "elsewhere", "status": "todo"}}}


def backlog(molecules: dict = MOLECULES) -> Backlog:
    root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
    for name, files in molecules.items():
        (root / name).mkdir(parents=True)
        for file_name, body in files.items():
            (root / name / file_name).write_text(cardfile.dump(body), "utf-8")
    return Backlog(root)


class TheEffectiveGraphIsValidated(unittest.TestCase):
    def setUp(self) -> None:
        self.book = backlog()
        self.rows = self.book.tasks()

    def card(self, task_id: str) -> dict:
        return next(row for row in self.rows if row["id"] == task_id)

    def test_the_tree_really_restores_the_wait_a_rewrite_would_drop(self):
        """The refusal is about the format, so the format is asked, not assumed:
        M.b drops its needs, and the next read hands back M.b → M.a → X → M.b."""
        self.book.set_status("M.b", "todo", needs=[])
        self.assertEqual(["M.a"], self.book.task("M.b")["needs"])
        self.assertEqual(["X"], self.book.task("M.a")["needs"])
        self.assertEqual(["M.b"], self.book.task("X")["needs"])

    def test_a_rewrite_that_drops_a_derived_wait_is_refused(self):
        refused = check_rewrite(self.card("M.b"), self.rows, {**CODE, "needs": []},
                                tree=self.book.path)
        self.assertIn("M.a", refused)

    def test_a_rewrite_that_waits_on_a_later_atom_is_refused(self):
        refused = check_rewrite(self.card("M.a"), self.rows, {**CODE, "needs": ["M.b"]},
                                tree=self.book.path)
        self.assertIn("M.b", refused)

    def test_the_molecule_cannot_drop_the_atoms_it_waits_for(self):
        refused = check_rewrite(self.card("M"), self.rows,
                                {**CODE, "files": [], "needs": []}, tree=self.book.path)
        self.assertIn("M.a", refused)

    def test_a_rewrite_stating_the_waits_the_tree_gives_it_is_accepted(self):
        book = backlog(STRAIGHT)
        rows = book.tasks()
        card = next(row for row in rows if row["id"] == "M.b")
        self.assertEqual("", check_rewrite(card, rows, {**CODE, "needs": ["M.a"]},
                                           tree=book.path))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
