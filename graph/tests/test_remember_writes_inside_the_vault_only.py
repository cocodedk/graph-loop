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
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import remember
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 10


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
        self.assertEqual(1, counts["untouched"])

    def test_it_is_reported_rather_than_done_quietly(self):
        """A molecule folder that is a link is refused for being one, before
        where it leads is even asked — it is the stronger of the two rules."""
        root = pathlib.Path(tempfile.mkdtemp()) / "vault"
        root.mkdir(parents=True)
        away = outside()
        molecule(away)
        (root / "T30").symlink_to(away, target_is_directory=True)
        said = remember.write_memory(root, log())["said"]["T30"]
        self.assertIn("symlink", said)


class AMoleculeSeenTwiceIsExportedOnce(unittest.TestCase):
    """`vault/T00 -> vault/T30` resolves INSIDE the vault, so containment says
    yes. The backlog then holds both names, T00 wrote T30's notes with T00's
    backlinks, and T30 found a note that was not its own and kept it — losing
    its own history to a link somebody made."""

    def setUp(self):
        self.root = vault()
        (self.root / "T00").symlink_to(self.root / "T30", target_is_directory=True)
        self.counts = remember.write_memory(self.root, [
            {"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
             "added": ["T00", "T00.schema", "T30", "T30.schema"]}])

    def test_the_real_folder_keeps_its_own_name_in_its_notes(self):
        text = (self.root / "T30" / "relatives" / "memory-01-schema.md").read_text("utf-8")
        self.assertIn("[[T30/01-schema]]", text)
        self.assertNotIn("[[T00/", text)

    def test_the_linked_name_is_skipped_and_said(self):
        self.assertIn("symlink", self.counts["said"]["T00"])


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


class ATempNamePlantedMidWriteIsNotFollowed(unittest.TestCase):
    def test_a_symlink_appearing_after_the_check_truncates_nothing(self):
        """The existence check and the write are two moments. A link planted
        between them was opened by name and its target emptied."""
        root = vault()
        card = root / "T30" / "01-schema.md"
        was = card.read_bytes()
        (root / "T30" / "relatives").mkdir()
        real = remember.render

        def planting(target, sections):
            # at the temp name of the card being written this very moment
            beside = (root / "T30" / "relatives" /
                      f".memory-{target.rsplit('/', 1)[1]}.md.tmp")
            if not beside.exists() and not beside.is_symlink():
                beside.symlink_to(card)      # somebody plants it, right now
            return real(target, sections)

        with mock.patch.object(remember, "render", planting):
            counts = remember.write_memory(root, log())
        self.assertEqual(was, card.read_bytes())
        self.assertIn("temp file", counts["said"]["T30.schema"])


class AMoleculeItCannotReadIsSkippedNotCrashedOn(unittest.TestCase):
    def test_a_symlinked_molecule_is_refused_before_anything_in_it_is_read(self):
        """Its own `molecule.md` need not even be a card: the folder is
        refused for being a link, and nothing inside it is opened."""
        root = vault()
        away = outside()
        away.mkdir(parents=True)
        (away / cardfile.HEAD).write_text("no front matter at all\n", "utf-8")
        (root / "T00").symlink_to(away, target_is_directory=True)
        counts = remember.write_memory(root, log())
        self.assertIn("symlink", counts["said"]["T00"])
        self.assertTrue((root / "T30" / "relatives" / "memory-01-schema.md").exists())

    def test_a_molecule_whose_atoms_do_not_read_is_skipped_and_said(self):
        root = vault()
        stray = root / "T31"
        stray.mkdir()
        (stray / cardfile.HEAD).write_text(
            cardfile.dump({"goal": "a lone piece", "status": "todo"}), "utf-8")
        (stray / "not-an-atom.md").write_text("this carries no order\n", "utf-8")
        counts = remember.write_memory(root, log())
        self.assertIn("could not be read", counts["said"]["T31"])
        self.assertTrue((root / "T30" / "relatives" / "memory-01-schema.md").exists())


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
