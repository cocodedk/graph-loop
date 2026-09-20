"""A memory note holds two kinds of section, and `remember` owns only one.

Every section the command writes ends its heading with `remember_note.MARK`.
Every other `## ` section was written by a person: it comes back where it sat,
with its own bytes, however far the log has grown past it. The control is the
other direction — a heading that carries the marker is the command's, and the
command takes it over, which is the one rule a person writing here must know.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import remember
import remember_note
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 8

MINE = "## 2026-09-21 — I looked at this by hand\n\nthe schema wants a second field."


def vault() -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp()) / "vault"
    piece = root / "T30"
    piece.mkdir(parents=True)
    (piece / cardfile.HEAD).write_text(
        cardfile.dump({"goal": "a piece", "status": "sliced"}), "utf-8")
    (piece / "01-schema.md").write_text(
        cardfile.dump({"goal": "the field exists", "status": "todo"}), "utf-8")
    return root


def first() -> list[dict]:
    return [{"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
             "added": ["T30", "T30.schema"]}]


def then() -> list[dict]:
    """The same log, one gate run longer."""
    return first() + [
        {"at": "2026-09-22T07:05:30Z", "kind": "step", "task": "T30.schema",
         "step": "gate", "seconds": 8.25, "passed": True, "code": 0}]


def note(root: pathlib.Path) -> pathlib.Path:
    return root / "T30" / "relatives" / "memory-01-schema.md"


class APersonsSectionIsKeptWhereItWas(unittest.TestCase):
    def setUp(self):
        self.root = vault()
        remember.write_memory(self.root, first())
        self.path = note(self.root)
        self.path.write_text(self.path.read_text("utf-8").rstrip("\n") + "\n\n" + MINE + "\n",
                             "utf-8")

    def test_it_comes_back_with_its_own_bytes(self):
        remember.write_memory(self.root, first())
        self.assertIn(MINE, self.path.read_text("utf-8"))

    def test_the_log_growing_past_it_leaves_it_where_the_person_put_it(self):
        remember.write_memory(self.root, then())
        text = self.path.read_text("utf-8")
        self.assertIn(MINE, text)
        self.assertLess(text.index("planned"), text.index("I looked at this"))
        self.assertLess(text.index("I looked at this"), text.index("the gate ran"))

    def test_keeping_it_is_idempotent(self):
        remember.write_memory(self.root, then())
        before = self.path.read_bytes()
        counts = remember.write_memory(self.root, then())
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(0, counts["written"])


class AMarkedHeadingIsTheCommandsOwn(unittest.TestCase):
    """The control: the discriminator has to work in both directions."""

    def test_a_persons_heading_that_carries_the_marker_is_taken_over(self):
        root = vault()
        remember.write_memory(root, first())
        path = note(root)
        stolen = f"## 2026-09-21 — mine, badly named{remember_note.MARK}"
        path.write_text(path.read_text("utf-8").rstrip("\n") + "\n\n" + stolen +
                        "\n\nthis text is not safe here.\n", "utf-8")
        remember.write_memory(root, first())
        self.assertNotIn("mine, badly named", path.read_text("utf-8"))

    def test_every_heading_the_command_writes_carries_the_marker(self):
        root = vault()
        remember.write_memory(root, then())
        headings = [line for line in note(root).read_text("utf-8").splitlines()
                    if line.startswith("## ")]
        self.assertEqual(["## Node"], [line for line in headings
                                       if not line.endswith(remember_note.MARK)])


class ASectionAtTheVeryEndIsKeptToo(unittest.TestCase):
    def test_a_last_section_with_no_trailing_newline_survives_the_log_growing(self):
        root = vault()
        remember.write_memory(root, first())
        path = note(root)
        path.write_text(path.read_text("utf-8").rstrip("\n") + "\n\n" + MINE, "utf-8")
        remember.write_memory(root, then())
        text = path.read_text("utf-8")
        self.assertIn(MINE, text)
        self.assertTrue(text.endswith("\n"), "the note still ends in one newline")

    def test_a_section_the_person_put_first_stays_first(self):
        root = vault()
        remember.write_memory(root, first())
        path = note(root)
        head, _, rest = path.read_text("utf-8").partition("\n## 2026-09-20")
        path.write_text(f"{head}\n\n{MINE}\n\n## 2026-09-20{rest}", "utf-8")
        remember.write_memory(root, then())
        text = path.read_text("utf-8")
        self.assertLess(text.index("I looked at this"), text.index("planned"))


class ANoteThatIsNotTextIsLeftExactlyAsItIs(unittest.TestCase):
    def test_a_note_that_will_not_decode_is_counted_and_never_rewritten(self):
        """Rewriting it would need reading it, and what cannot be read cannot
        be told apart into the command's sections and a person's."""
        root = vault()
        remember.write_memory(root, first())
        path = note(root)
        path.write_bytes(b"---\nkind: memory\n---\n\n## Node\n\n- \xff\xfe not text\n")
        before = path.read_bytes()
        counts = remember.write_memory(root, then())
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(1, counts["left_alone"])


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
