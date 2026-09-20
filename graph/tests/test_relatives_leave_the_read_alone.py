"""A relative never enters what `backlog_tree.read`, `write` or `cardfile.linker`
produce, and a note left beside a card's atoms fails loudly instead of silently.

`molecule.ordered` skips a sub-folder and stops the whole read on any `.md` file
it cannot number, so a `relatives/` folder must sit where it is skipped and
never beside the atoms it is about. This guards both directions: a relatives
folder, wherever it is placed, changes nothing the tree reads, writes or
resolves; the same note dropped beside the atoms instead raises, which is the
case this convention exists to avoid.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import backlog_tree
import cardfile
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

MEMORY = """---
kind: memory
node: "[[T30/molecule]]"
---

## Node

- [[T30/molecule]]

## 2026-09-20

tried the first shape, see 01-schema
"""

LEARNING = """---
kind: learning
node: "[[T30/molecule]]"
status: open
applies_to: project
basis: design
---

## Node

- [[T30/molecule]]

## Rule

split the schema atom before the producer next time
"""

EXPECTED_TESTS = 6


def vault() -> pathlib.Path:
    """T30, a molecule of two atoms, and T31, a molecule of one."""
    root = pathlib.Path(tempfile.mkdtemp()) / "vault"
    t30 = root / "T30"
    t30.mkdir(parents=True)
    (t30 / cardfile.HEAD).write_text(
        cardfile.dump({"goal": "a piece", "status": "sliced"}), "utf-8")
    (t30 / "01-schema.md").write_text(
        cardfile.dump({"goal": "the field exists", "status": "todo"}), "utf-8")
    (t30 / "02-producer.md").write_text(
        cardfile.dump({"goal": "the record carries it", "status": "todo"}), "utf-8")
    t31 = root / "T31"
    t31.mkdir()
    (t31 / cardfile.HEAD).write_text(
        cardfile.dump({"goal": "a lone piece", "status": "todo"}), "utf-8")
    return root


def rows(root: pathlib.Path) -> dict:
    return {row["id"]: row for row in backlog_tree.read(root)["tasks"]}


class ARelativesFolderIsInvisibleToRead(unittest.TestCase):
    def setUp(self):
        self.root = vault()
        self.before = rows(self.root)

    def test_a_relatives_folder_inside_a_molecule_changes_nothing_read(self):
        relatives = self.root / "T30" / "relatives"
        relatives.mkdir()
        (relatives / "memory-T30.md").write_text(MEMORY, "utf-8")
        (relatives / "learning-T30-schema-first.md").write_text(LEARNING, "utf-8")
        self.assertEqual(self.before, rows(self.root))

    def test_a_relatives_folder_at_the_vault_root_changes_nothing_read(self):
        relatives = self.root / "relatives"
        relatives.mkdir()
        (relatives / "memory-vault.md").write_text(MEMORY, "utf-8")
        self.assertEqual(self.before, rows(self.root))


class ALinkerNeverResolvesARelative(unittest.TestCase):
    def setUp(self):
        self.root = vault()
        self.before = cardfile.linker(self.root)("T30.schema")

    def test_the_linker_resolves_the_same_name_with_relatives_present(self):
        relatives = self.root / "T30" / "relatives"
        relatives.mkdir()
        (relatives / "memory-T30.md").write_text(MEMORY, "utf-8")
        self.assertEqual(self.before, cardfile.linker(self.root)("T30.schema"))

    def test_the_linker_never_resolves_a_relatives_own_name(self):
        relatives = self.root / "T30" / "relatives"
        relatives.mkdir()
        (relatives / "memory-T30.md").write_text(MEMORY, "utf-8")
        link = cardfile.linker(self.root)
        self.assertEqual("memory-T30", link("memory-T30"))


class AWriteRoundTripLeavesRelativesUntouched(unittest.TestCase):
    def test_every_file_under_relatives_is_byte_for_byte_unchanged(self):
        root = vault()
        relatives = root / "T30" / "relatives"
        relatives.mkdir()
        memory_path = relatives / "memory-T30.md"
        memory_path.write_bytes(MEMORY.encode("utf-8"))
        before = memory_path.read_bytes()
        backlog_tree.write(root, backlog_tree.read(root))
        self.assertEqual(before, memory_path.read_bytes())


class ANoteBesideTheAtomsStopsTheRead(unittest.TestCase):
    def test_the_same_memory_note_placed_beside_the_atoms_raises(self):
        """The control: the case this convention exists to avoid, made to fail
        in front of you, as a new check in this repository must be."""
        root = vault()
        (root / "T30" / "memory-T30.md").write_text(MEMORY, "utf-8")
        with self.assertRaises(ValueError) as caught:
            backlog_tree.read(root)
        self.assertIn("memory-T30.md", str(caught.exception))


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
