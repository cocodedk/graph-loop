"""A stage number is a number: a molecule may hold more than 99 atoms.

astra's round-2 review, finding 11. Two places read the number in front of an
atom's file name, and both stopped at two digits:

  * `molecule.ordered` sorted the file names as text, so `100-b.md` came
    before `99-a.md` and the tree derived the waits backwards;
  * `backlog_tree._outside` matched `[0-9][0-9]-*.yaml`, so a three-digit
    sibling was not recognised as an atom of this folder and the parent wrote
    it down as a need from outside — which the next read turns into a circle.
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

EXPECTED_TESTS = 2


def wide() -> Backlog:
    """One molecule whose atoms cross the hundred: 99 runs, then 100."""
    root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
    (root / "M").mkdir(parents=True)
    for name, body in (("molecule.md", {"goal": "the piece", "status": "sliced"}),
                       ("99-a.md", {"goal": "first", "status": "todo"}),
                       ("100-b.md", {"goal": "second", "status": "todo"})):
        (root / "M" / name).write_text(cardfile.dump(body), "utf-8")
    return Backlog(root)


class TheNumberIsANumber(unittest.TestCase):
    def test_atom_100_waits_for_atom_99_and_not_the_other_way_round(self):
        rows = {row["id"]: row for row in wide().tasks()}
        self.assertEqual([], rows["M.a"]["needs"])
        self.assertEqual(["M.a"], rows["M.b"]["needs"])

    def test_the_piece_does_not_write_a_three_digit_atom_down_as_an_outside_need(self):
        backlog = wide()
        backlog.set_status("M", "done")
        body = cardfile.load(backlog.path / "M" / "molecule.md")
        self.assertNotIn("needs", body)


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
