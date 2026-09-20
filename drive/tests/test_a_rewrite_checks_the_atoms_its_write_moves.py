"""A rewrite is judged on every card its write re-aims, not only its own.

A molecule's `needs` are what its first-stage atoms inherit, so writing them
moves the atoms too. Re-deriving the written card alone accepted `M.needs =
[X, M.a]` — representable, and harmless where M sits — while the next read gave
M.a the wait on X that closes M.a → X → M.a, and no reader had looked at M.a
(an independent review, finding 2).
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

EXPECTED_TESTS = 3
# X waits for the atom, and the molecule waits for nothing yet: the circle
# arrives the moment the molecule's own file starts waiting for X.
MOLECULES: dict = {
    "M": {"molecule.md": {"goal": "the piece", "status": "rejected",
                            "refused_why": "the reviewer never answered"},
          "01-a.md": {"goal": "first", "status": "todo", **CODE}},
    "X": {"molecule.md": {"goal": "elsewhere", "status": "todo", "needs": ["M.a"]}},
}
WIDER = {**CODE, "files": [], "needs": ["X", "M.a"]}


def backlog() -> Backlog:
    root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
    for name, files in MOLECULES.items():
        (root / name).mkdir(parents=True)
        for file_name, body in files.items():
            (root / name / file_name).write_text(cardfile.dump(body), "utf-8")
    return Backlog(root)


class TheAtomsAreChecked(unittest.TestCase):
    def setUp(self) -> None:
        self.book = backlog()
        self.rows = self.book.tasks()

    def test_the_write_really_puts_the_circle_through_the_atom(self):
        """The refusal is about what the tree does, so the tree is asked."""
        self.book.set_status("M", "todo", needs=["X", "M.a"])
        self.assertEqual(["X"], self.book.task("M.a")["needs"])
        self.assertEqual(["M.a"], self.book.task("X")["needs"])

    def test_a_rewrite_that_strands_an_atom_it_re_aims_is_refused(self):
        card = next(row for row in self.rows if row["id"] == "M")
        self.assertIn("M.a", check_rewrite(card, self.rows, WIDER, tree=self.book.path))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
