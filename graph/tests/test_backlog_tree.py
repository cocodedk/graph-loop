"""The same backlog, kept as a tree of molecules instead of one file.

Every id reads exactly as it did in the file: `molecule.md` is the piece
itself, so `T26` is the folder and `T26.schema` is an atom inside it, and no
`needs` anywhere else has to be re-pointed.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog

ONE = {
    "T26": {
        "molecule.md": {"goal": "the board can say completed", "status": "sliced"},
        "01-schema.md": {"goal": "the field exists", "status": "todo"},
        "02-producer.md": {"goal": "the record carries it", "status": "todo"},
        "03-reader.md": {"goal": "the rule reads it", "status": "todo",
                           "needs": ["T4.signin"]}},
    "T25": {"molecule.md": {"goal": "the kill exit", "status": "todo"}},
}


def tree(molecules: dict) -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
    root.mkdir()
    for name, files in molecules.items():
        folder = root / name
        folder.mkdir()
        for file_name, body in files.items():
            (folder / file_name).write_text(cardfile.dump(body), "utf-8")
    return root


EXPECTED_TESTS = 18


class ATreeReadsAsABacklog(unittest.TestCase):
    def setUp(self):
        self.backlog = Backlog(tree(ONE))
        self.rows = {row["id"]: row for row in self.backlog.tasks()}

    def test_the_piece_and_its_atoms_keep_the_ids_the_file_gave_them(self):
        self.assertEqual(sorted(self.rows),
                         ["T25", "T26", "T26.producer", "T26.reader", "T26.schema"])

    def test_a_molecule_of_one_is_just_the_piece(self):
        self.assertEqual(self.rows["T25"]["needs"], [])

    def test_each_atom_waits_for_every_atom_with_a_lower_number(self):
        self.assertEqual(self.rows["T26.schema"]["needs"], [])
        self.assertEqual(self.rows["T26.producer"]["needs"], ["T26.schema"])

    def test_the_piece_waits_for_every_atom_as_a_sliced_task_always_has(self):
        self.assertEqual(self.rows["T26"]["needs"],
                         ["T26.schema", "T26.producer", "T26.reader"])

    def test_a_need_outside_the_molecule_is_kept_beside_the_order(self):
        self.assertEqual(self.rows["T26.reader"]["needs"],
                         ["T26.schema", "T26.producer", "T4.signin"])

    def test_atoms_sharing_a_number_run_side_by_side(self):
        folder = self.backlog.path / "T10"
        folder.mkdir()
        for name, body in (("molecule.md", {"goal": "counts", "status": "umbrella"}),
                           ("01-counts.md", {"goal": "the count", "status": "todo"}),
                           ("02-gates.md", {"goal": "a gate", "status": "todo"}),
                           ("02-paths.md", {"goal": "a path", "status": "todo"})):
            (folder / name).write_text(cardfile.dump(body), "utf-8")
        rows = {row["id"]: row for row in self.backlog.tasks()}
        self.assertEqual(rows["T10.gates"]["needs"], ["T10.counts"])
        self.assertEqual(rows["T10.paths"]["needs"], ["T10.counts"])

    def test_an_atom_knows_the_piece_it_was_sliced_from(self):
        self.assertEqual(self.rows["T26.schema"]["sliced_from"], "T26")

    def test_only_the_first_atom_and_the_lone_piece_can_start(self):
        self.assertEqual(sorted(row["id"] for row in self.backlog.startable()),
                         ["T25", "T26.schema"])

    def test_a_molecule_still_being_built_is_not_read(self):
        half = self.backlog.path / ".building-e2e-board"
        half.mkdir()
        (half / "molecule.md").write_text(cardfile.dump({"goal": "x", "status": "todo"}), "utf-8")
        self.assertEqual(len(self.backlog.tasks()), 5)

    def test_a_folder_with_no_molecule_file_is_not_a_molecule(self):
        (self.backlog.path / "notes").mkdir()
        self.assertEqual(len(self.backlog.tasks()), 5)


class WritingTouchesOneFile(unittest.TestCase):
    def setUp(self):
        self.backlog = Backlog(tree(ONE))

    def body(self, *names) -> dict:
        return cardfile.load(self.backlog.path.joinpath(*names))

    def test_a_status_lands_in_that_atom_s_own_file(self):
        self.backlog.set_status("T26.producer", "done")
        self.assertEqual(self.body("T26", "02-producer.md")["status"], "done")

    def test_the_piece_s_own_status_lands_in_molecule_yaml(self):
        self.backlog.set_status("T26", "done")
        self.assertEqual(self.body("T26", "molecule.md")["status"], "done")

    def test_nothing_the_tree_derives_is_written_back(self):
        self.backlog.set_status("T26.schema", "done")
        body = self.body("T26", "01-schema.md")
        for derived in ("id", "needs", "sliced_from"):
            self.assertNotIn(derived, body)

    def test_a_need_from_outside_survives_the_round_trip(self):
        self.backlog.set_status("T26.reader", "done")
        self.assertEqual(self.body("T26", "03-reader.md")["needs"], ["T4.signin"])

    def test_the_piece_does_not_write_its_atoms_down_as_needs(self):
        self.backlog.set_status("T26", "done")
        self.assertNotIn("needs", self.body("T26", "molecule.md"))

    def test_a_piece_cut_from_another_piece_keeps_saying_so(self):
        path = self.backlog.path / "T26" / "04-v2.md"
        path.write_text(cardfile.dump(
            {"goal": "a second try", "status": "todo", "sliced_from": "T26.reader"}), "utf-8")
        self.backlog.set_status("T26.v2", "done")
        self.assertEqual(cardfile.load(path)["sliced_from"], "T26.reader")

    def test_a_row_with_no_file_is_refused_rather_than_dropped(self):
        with self.assertRaises(KeyError):
            self.backlog.slice_task("T25", [{"goal": "a piece"}])

    def test_only_the_changed_file_is_touched(self):
        """One card's status must not rewrite every molecule in the backlog:
        112 unchanged files paid for one card's status write before this held."""
        backlog = Backlog(tree({
            "T1": {"molecule.md": {"goal": "one", "status": "todo"}},
            "T2": {"molecule.md": {"goal": "two", "status": "todo"}},
            "T3": {"molecule.md": {"goal": "three", "status": "todo"}},
        }))
        files = sorted(backlog.path.rglob("molecule.md"))
        before = {path: path.stat().st_mtime_ns for path in files}
        time.sleep(0.01)
        backlog.set_status("T2", "done")
        changed = [path for path in files if path.stat().st_mtime_ns != before[path]]
        self.assertEqual([backlog.path / "T2" / "molecule.md"], changed)


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
