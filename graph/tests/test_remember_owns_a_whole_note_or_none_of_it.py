"""A note is the command's, whole, or it is not the command's at all.

Four rounds of review found the same thing four ways: the command read a
person's Markdown to work out which parts were its own, and each round found
another spelling it read wrong — a heading after a tab, a heading hidden by an
inline pair of backticks the scanner took for a fence — and each time somebody's
text was deleted. Parsing Markdown by hand to decide what to delete is the
defect; no amount of scanner is the fix.

So there is no scanner. The note the command writes carries a digest of its own
body, and a file is the command's to rewrite only when it is byte for byte what
the command last wrote. One edit of any kind, anywhere — a heading, a space, a
front-matter key, one byte — and the file is a person's: it is kept exactly as
it is and the run says `kept: edited by hand`.
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
             "added": ["T30", "T30.schema"]}]


def grown() -> list[dict]:
    return log() + [{"at": "2026-09-22T07:05:30Z", "kind": "step", "task": "T30.schema",
                     "step": "gate", "seconds": 8.25, "passed": True, "code": 0}]


def note(root: pathlib.Path) -> pathlib.Path:
    return root / "T30" / "relatives" / "memory-01-schema.md"


def touched(edit) -> tuple[pathlib.Path, pathlib.Path, bytes]:
    """A note the command wrote, then edited by hand the way `edit` says."""
    root = vault()
    remember.write_memory(root, log())
    path = note(root)
    path.write_bytes(edit(path.read_text("utf-8")).encode("utf-8"))
    return root, path, path.read_bytes()


HANDS = {
    # the H2 the scanner missed because a tab, not a space, follows the hashes
    "a heading written after a tab": lambda was: was + "\n##\tPersonal notes\n\nkeep me.\n",
    # an inline pair of backticks the scanner read as an opening fence
    "a heading after inline backticks": lambda was: (
        was + "\nsee `` `inline code` `` and ```inline```\n\n## Personal notes\n\nkeep me.\n"),
    "one space at the end of a line": lambda was: was.replace("## Node\n", "## Node \n", 1),
    "a front-matter key of their own": lambda was: was.replace(
        "kind: memory\n", "kind: memory\ntags: [mine]\n", 1),
    "the whole file emptied": lambda was: "",
    "a node aimed at another card": lambda was: was.replace(
        "[[T30/01-schema]]", "[[T30/01-schema-elsewhere]]"),
}


class AHandEditedNoteIsNeverRewritten(unittest.TestCase):
    def test_none_of_these_edits_is_touched_again(self):
        for what, edit in HANDS.items():
            with self.subTest(what):
                root, path, was = touched(edit)
                counts = remember.write_memory(root, grown())
                self.assertEqual(was, path.read_bytes())
                self.assertEqual(1, counts["untouched"])

    def test_each_of_them_is_reported_as_edited_by_hand(self):
        for what, edit in HANDS.items():
            with self.subTest(what):
                root, _, _ = touched(edit)
                self.assertEqual("kept: edited by hand",
                                 remember.write_memory(root, grown())["said"]["T30.schema"])

    def test_an_empty_file_that_was_already_there_is_one_of_them(self):
        """It used to be read as no file at all, and gained a whole note."""
        root = vault()
        note(root).parent.mkdir(parents=True)
        note(root).write_bytes(b"")
        counts = remember.write_memory(root, log())
        self.assertEqual(b"", note(root).read_bytes())
        self.assertEqual(1, counts["untouched"])


class ANoteItWroteItselfStaysItsOwn(unittest.TestCase):
    def test_a_note_it_wrote_is_refreshed_when_the_log_grows(self):
        root = vault()
        remember.write_memory(root, log())
        counts = remember.write_memory(root, grown())
        self.assertEqual(1, counts["written"])
        self.assertIn("the gate ran, exit 0", note(root).read_text("utf-8"))

    def test_the_same_log_writes_nothing_the_second_time(self):
        root = vault()
        remember.write_memory(root, grown())
        before = note(root).read_bytes()
        counts = remember.write_memory(root, grown())
        self.assertEqual(before, note(root).read_bytes())
        self.assertEqual(0, counts["written"])

    def test_a_note_thrown_away_is_rebuilt_byte_for_byte(self):
        root = vault()
        remember.write_memory(root, grown())
        before = note(root).read_bytes()
        note(root).unlink()
        remember.write_memory(root, grown())
        self.assertEqual(before, note(root).read_bytes())


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
