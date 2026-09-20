"""Two rules, decided once: whose note this is, and hands off its front matter.

Three separate attempts to add a missing key to front matter that was already
there each broke a valid note — a flow mapping, then a block indented two
spaces, then one closed with an explicit `...`. YAML has more valid spellings
than a text edit can know about, and reading it into a mapping and writing it
back loses the order, the quoting and the comments somebody chose. So the
command stopped trying: a note it MAKES gets `kind` and `node`, a note that
exists keeps its bytes, and the summary says what is missing.

Whose note it is, is one conservative question asked in one place. No `node`
at all means it is this card's by where it sits. A `node` that is a string and
exactly this card's link means the same. Anything else — a list, a number,
another card's link, front matter that will not parse — means it is not ours,
and a list is the one that slipped through a guard that only looked at strings.
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
import yaml  # type: ignore[import-untyped]

EXPECTED_TESTS = 11

HISTORY = """
## Node

- [[T30/01-schema-elsewhere]]

## 2026-09-01 — what this note was about before — from the log

2026-09-01T09:00:00Z. The plan phase added this card.
"""

NOT_OURS = {
    "a list": '---\nkind: memory\nnode: ["[[T30/01-schema-elsewhere]]"]\n---\n',
    "a number": "---\nkind: memory\nnode: 41\n---\n",
    "another card": '---\nkind: memory\nnode: "[[T30/01-schema-elsewhere]]"\n---\n',
    "broken yaml": "---\nkind: memory\nnode: [unclosed\n---\n",
    "not a mapping": "---\n- kind: memory\n- node: nowhere\n---\n",
}

VAULTWIDE = """---
# the properties this vault queries, on every note
tags: ["logic-contracts", "tempo"]
status: open
priority: null
kind: memory
node: "[[T30/01-schema]]"
---

## Node

- [[T30/01-schema]]
"""

KEPT = {
    "indented two spaces": "---\n  kind: memory\n---\n",
    "closed with a terminator": "---\nkind: memory\n...\n---\n",
    "flow style": "---\n{kind: memory, tags: [keep]}\n---\n",
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
             "added": ["T30", "T30.schema"]}]


def note(root: pathlib.Path) -> pathlib.Path:
    return root / "T30" / "relatives" / "memory-01-schema.md"


def given(text: str) -> tuple[pathlib.Path, pathlib.Path]:
    root = vault()
    note(root).parent.mkdir(parents=True)
    note(root).write_text(text, "utf-8")
    return root, note(root)


class ANoteThisCardCannotClaimIsNotWritten(unittest.TestCase):
    def test_none_of_these_notes_changes_a_byte(self):
        for what, front in NOT_OURS.items():
            with self.subTest(what):
                root, path = given(front.rstrip("\n") + "\n" + HISTORY)
                was = path.read_bytes()
                counts = remember.write_memory(root, log())
                self.assertEqual(was, path.read_bytes())
                self.assertEqual(1, counts["untouched"])

    def test_each_of_them_is_said_out_loud(self):
        for what, front in NOT_OURS.items():
            with self.subTest(what):
                root, _ = given(front.rstrip("\n") + "\n" + HISTORY)
                said = remember.write_memory(root, log())["said"]["T30.schema"]
                self.assertIn("nothing here was changed", said)


class FrontMatterThatIsThereIsNeverEdited(unittest.TestCase):
    def test_every_spelling_of_it_comes_back_byte_for_byte(self):
        for what, front in KEPT.items():
            with self.subTest(what):
                root, path = given(front)
                was = cardfile.FRONT.match(path.read_text("utf-8"))["front"]
                remember.write_memory(root, log())
                self.assertEqual(was, cardfile.FRONT.match(
                    path.read_text("utf-8"))["front"])

    def test_every_one_of_them_still_parses_afterwards(self):
        for what, front in KEPT.items():
            with self.subTest(what):
                root, path = given(front)
                remember.write_memory(root, log())
                yaml.safe_load(cardfile.FRONT.match(path.read_text("utf-8"))["front"])

    def test_the_missing_key_is_said_rather_than_added(self):
        root, _ = given(KEPT["indented two spaces"])
        said = remember.write_memory(root, log())["said"]["T30.schema"]
        self.assertIn("node", said)
        self.assertIn("never edited", said)

    def test_the_properties_a_whole_vault_queries_are_still_there(self):
        """A vault carries a property set on every note and queries it across
        the vault; a comment, an order and a quoting style are part of it."""
        root, path = given(VAULTWIDE)
        remember.write_memory(root, log())
        kept = cardfile.FRONT.match(path.read_text("utf-8"))["front"]
        for line in ("tags:", "status: open", "priority: null",
                     "# the properties this vault queries, on every note"):
            self.assertIn(line, kept)

    def test_that_set_is_the_same_text_after_two_runs(self):
        root, path = given(VAULTWIDE)
        was = cardfile.FRONT.match(path.read_text("utf-8"))["front"]
        remember.write_memory(root, log())
        remember.write_memory(root, log())
        self.assertEqual(was, cardfile.FRONT.match(path.read_text("utf-8"))["front"])

    def test_the_sections_are_still_refreshed_under_it(self):
        root, path = given(KEPT["indented two spaces"])
        remember.write_memory(root, log())
        self.assertIn("planned — from the log", path.read_text("utf-8"))


class ANoteTheCommandMakesGetsBothKeys(unittest.TestCase):
    def test_a_note_that_did_not_exist_carries_kind_and_node(self):
        root = vault()
        remember.write_memory(root, log())
        self.assertEqual(["kind: memory", "node: '[[T30/01-schema]]'"],
                         cardfile.FRONT.match(
                             note(root).read_text("utf-8"))["front"].splitlines())

    def test_a_file_with_no_front_matter_is_left_alone_not_given_any(self):
        """It used to be given some, which let a foreign note be claimed:
        without front matter nothing says whose note it is."""
        root, path = given("## 2026-09-21 — mine\n\nno front matter here.\n")
        was = path.read_bytes()
        counts = remember.write_memory(root, log())
        self.assertEqual(was, path.read_bytes())
        self.assertEqual(1, counts["untouched"])

    def test_the_note_it_makes_itself_is_the_same_on_the_next_run(self):
        root = vault()
        remember.write_memory(root, log())
        before = note(root).read_bytes()
        remember.write_memory(root, log())
        self.assertEqual(before, note(root).read_bytes())


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
