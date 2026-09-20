"""Every path is resolved, and nothing outside the vault is written.

Checking the note, its folder and the durable write's temporary sibling was not
enough: a molecule folder that was itself a symlink took both of its memory
notes out of the vault entirely, because no ancestor was looked at (an
independent review). So the real path is asked of the filesystem and must lie
inside the resolved vault root — and no symlink on the way is followed, which
is a second thing: a link pointing back INSIDE the vault resolves fine and
would still let a write land on a card.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import remember
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 5


def molecule(folder: pathlib.Path) -> None:
    folder.mkdir(parents=True)
    (folder / cardfile.HEAD).write_text(
        cardfile.dump({"goal": "a piece", "status": "sliced"}), "utf-8")
    (folder / "01-schema.md").write_text(
        cardfile.dump({"goal": "the field exists", "status": "todo"}), "utf-8")


def vault() -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp()) / "vault"
    molecule(root / "T30")
    return root


def log() -> list[dict]:
    return [{"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
             "added": ["T30", "T30.schema"]}]


def outside() -> pathlib.Path:
    return pathlib.Path(tempfile.mkdtemp()) / "elsewhere"


class AMoleculeThatResolvesOutsideIsSkipped(unittest.TestCase):
    def test_a_symlinked_molecule_folder_takes_none_of_its_notes_with_it(self):
        root = pathlib.Path(tempfile.mkdtemp()) / "vault"
        root.mkdir(parents=True)
        away = outside()
        molecule(away)
        (root / "T30").symlink_to(away, target_is_directory=True)
        counts = remember.write_memory(root, log())
        self.assertEqual(sorted(path.name for path in away.iterdir()),
                         ["01-schema.md", "molecule.md"])
        self.assertEqual(2, counts["untouched"])

    def test_it_is_reported_rather_than_done_quietly(self):
        root = pathlib.Path(tempfile.mkdtemp()) / "vault"
        root.mkdir(parents=True)
        away = outside()
        molecule(away)
        (root / "T30").symlink_to(away, target_is_directory=True)
        said = remember.write_memory(root, log())["said"]["T30.schema"]
        self.assertIn("outside", said)


class NothingIsWrittenThroughASymlink(unittest.TestCase):
    def test_a_relatives_folder_that_is_a_symlink_is_not_written_into(self):
        root = vault()
        away = outside()
        away.mkdir()
        (root / "T30" / "relatives").symlink_to(away, target_is_directory=True)
        remember.write_memory(root, log())
        self.assertEqual([], list(away.iterdir()))

    def test_a_note_that_is_a_symlink_onto_a_card_leaves_the_card_alone(self):
        root = vault()
        card = root / "T30" / "01-schema.md"
        was = card.read_bytes()
        (root / "T30" / "relatives").mkdir()
        (root / "T30" / "relatives" / "memory-01-schema.md").symlink_to(card)
        remember.write_memory(root, log())
        self.assertEqual(was, card.read_bytes())

    def test_a_symlink_where_the_durable_write_puts_its_sibling_cannot_truncate(self):
        """`durable.replace` writes `.<name>.tmp` beside the note and renames."""
        root = vault()
        card = root / "T30" / "01-schema.md"
        was = card.read_bytes()
        (root / "T30" / "relatives").mkdir()
        (root / "T30" / "relatives" / ".memory-01-schema.md.tmp").symlink_to(card)
        counts = remember.write_memory(root, log())
        self.assertEqual(was, card.read_bytes())
        self.assertEqual(1, counts["untouched"])


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
