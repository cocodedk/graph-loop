"""When in doubt, do not write.

Three rounds of review found the same shape over and over: a file shaped a
little differently from what the command expected, and the command wrote it
anyway and lost something. So it stopped guessing. A note is refreshed only
when every one of a short list of things is true of its raw bytes, and anything
else is left exactly as it is, counted, and named in the summary.

The list is in `remember_read.understood`, and each line of it is here as a
case: UTF-8, no byte-order mark, LF endings only, front matter delimited by
plain `---` lines, front matter that parses, and every fence closed by the
rule — a closing fence is the same character, at least as long, with nothing
after it but spaces or tabs. A non-breaking space does not close a fence, and
a file whose fences are not all closed is not understood.

An existing file is never GIVEN front matter either. Without it there is
nothing to say whose note it is, and a foreign note was overwritten that way.

And nothing is written through a symlink: not the note, not the folder it sits
in, not the temporary sibling the durable write puts beside it — that one would
have let a card be truncated.
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

EXPECTED_TESTS = 6

HISTORY = ("\n## Node\n\n- [[T30/01-schema]]\n\n"
           "## 2026-09-01 — what happened before — from the log\n\n"
           "2026-09-01T09:00:00Z. The plan phase added this card.\n")

FENCED = ("---\nkind: memory\nnode: \"[[T30/01-schema]]\"\n---\n\n## Node\n\n"
          "- [[T30/01-schema]]\n\n## 2026-09-21 — mine\n\n```\n"
          "## 2026-09-20 — planned — from the log\n``` \n\nkeep this line.\n")

NOT_UNDERSTOOD = {
    # a fence closed by a non-breaking space is not closed at all
    "a fence closed with a non-breaking space": FENCED.encode("utf-8"),
    "no front matter at all": "## 2026-09-21 — mine\n\nno front matter.\n".encode(),
    "front matter nobody terminated": b"---\nkind: memory\nnode: nowhere\n",
    "carriage returns": ("---\r\nkind: memory\r\n---\r\n" + HISTORY).encode("utf-8"),
    "a byte-order mark": b"\xef\xbb\xbf" + ("---\nkind: memory\n---\n" + HISTORY).encode("utf-8"),
    "not utf-8": b"---\nkind: memory\n---\n\n## mine\n\n\xff\xfe not text\n",
    # the yaml parser raises ValueError, not YAMLError, on both of these
    "a node that is an impossible date": ("---\nkind: memory\nnode: 2026-99-99\n---\n"
                                          + HISTORY).encode("utf-8"),
    "a node cast to a type it is not": ("---\nkind: memory\nnode: !!int nonsense\n---\n"
                                        + HISTORY).encode("utf-8"),
}


def vault() -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp()) / "vault"
    piece = root / "T30"
    piece.mkdir(parents=True)
    (piece / cardfile.HEAD).write_text(
        cardfile.dump({"goal": "a piece", "status": "sliced"}), "utf-8")
    (piece / "01-schema.md").write_text(
        cardfile.dump({"goal": "the field exists", "status": "todo"}), "utf-8")
    return root


def log() -> list[dict]:
    return [{"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
             "added": ["T30", "T30.schema"]},
            {"at": "2026-09-22T07:05:30Z", "kind": "step", "task": "T30.schema",
             "step": "gate", "seconds": 8.25, "passed": True, "code": 0}]


def note(root: pathlib.Path) -> pathlib.Path:
    return root / "T30" / "relatives" / "memory-01-schema.md"


def given(raw: bytes) -> tuple[pathlib.Path, pathlib.Path]:
    root = vault()
    note(root).parent.mkdir(parents=True)
    note(root).write_bytes(raw)
    return root, note(root)


class AFileItDoesNotFullyUnderstandIsLeftAsItIs(unittest.TestCase):
    def test_not_one_of_these_files_changes_a_byte(self):
        for what, raw in NOT_UNDERSTOOD.items():
            with self.subTest(what):
                root, path = given(raw)
                counts = remember.write_memory(root, log())
                self.assertEqual(raw, path.read_bytes())
                self.assertEqual(1, counts["untouched"])

    def test_each_of_them_is_named_in_the_summary(self):
        for what, raw in NOT_UNDERSTOOD.items():
            with self.subTest(what):
                root, _ = given(raw)
                said = remember.write_memory(root, log())["said"]["T30.schema"]
                self.assertTrue(said.strip(), "a note left alone is always explained")

    def test_a_note_it_does_understand_is_still_refreshed(self):
        root, path = given(("---\nkind: memory\nnode: \"[[T30/01-schema]]\"\n---\n"
                            + HISTORY).encode("utf-8"))
        counts = remember.write_memory(root, log())
        self.assertEqual(0, counts["untouched"])
        self.assertIn("the gate ran, exit 0", path.read_text("utf-8"))


class NothingIsWrittenThroughASymlink(unittest.TestCase):
    def test_a_relatives_folder_that_is_a_symlink_is_not_written_into(self):
        root = vault()
        outside = pathlib.Path(tempfile.mkdtemp()) / "elsewhere"
        outside.mkdir()
        (root / "T30" / "relatives").symlink_to(outside, target_is_directory=True)
        counts = remember.write_memory(root, log())
        self.assertEqual([], list(outside.iterdir()))
        self.assertIn("symlink", counts["said"]["T30.schema"])

    def test_a_symlink_where_the_durable_write_puts_its_sibling_cannot_truncate(self):
        """`durable.replace` writes `.<name>.tmp` beside the note and renames.
        A symlink left at that name pointed the write at a card."""
        root = vault()
        card = root / "T30" / "01-schema.md"
        was = card.read_bytes()
        relatives = root / "T30" / "relatives"
        relatives.mkdir()
        (relatives / ".memory-01-schema.md.tmp").symlink_to(card)
        counts = remember.write_memory(root, log())
        self.assertEqual(was, card.read_bytes())
        self.assertEqual(1, counts["untouched"])

    def test_the_note_itself_being_a_symlink_is_not_followed(self):
        root = vault()
        card = root / "T30" / "01-schema.md"
        was = card.read_bytes()
        relatives = root / "T30" / "relatives"
        relatives.mkdir()
        (relatives / "memory-01-schema.md").symlink_to(card)
        remember.write_memory(root, log())
        self.assertEqual(was, card.read_bytes())


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
