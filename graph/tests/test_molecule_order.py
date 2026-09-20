"""A molecule declares its order once: in the names of its atom files."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import molecule
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit


def folder(*names) -> pathlib.Path:
    where = pathlib.Path(tempfile.mkdtemp()) / "outcome-facts"
    where.mkdir()
    for name in names:
        (where / name).write_text("goal: x\n", "utf-8")
    return where


EXPECTED_TESTS = 5


class TheFileNamesAreTheOrder(unittest.TestCase):
    def test_the_atoms_come_back_by_their_number(self):
        where = folder("02-producer.md", "01-schema.md", "10-last.md",
                       "molecule.md")
        self.assertEqual([p.name for p in molecule.ordered(where)],
                         ["01-schema.md", "02-producer.md", "10-last.md"])

    def test_an_atom_without_a_number_stops_the_read(self):
        with self.assertRaises(ValueError) as caught:
            molecule.ordered(folder("01-schema.md", "reader.md"))
        self.assertIn("reader.md", str(caught.exception))

    def test_a_molecule_of_one_is_a_molecule(self):
        self.assertEqual([p.name for p in molecule.ordered(folder("01-only.md"))],
                         ["01-only.md"])


class TheIdIsWhereItSits(unittest.TestCase):
    def test_the_id_is_the_folder_and_the_stem(self):
        self.assertEqual(molecule.atom_id("outcome-facts", "02-producer.md"),
                         "outcome-facts.producer")

    def test_a_file_that_is_not_an_atom_has_no_id(self):
        with self.assertRaises(ValueError):
            molecule.atom_id("outcome-facts", "molecule.md")


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
