"""The command owns the sections it marks, and two front-matter keys when the
note has none. Everything else in the file is the person's.

A vault carries properties across every note — Obsidian queries them — and the
first version of this rewrote a memory note's front matter from scratch on
every run, so a tag, a status or any property somebody put there was gone the
next time the command ran. Front matter is now kept as TEXT: never round-tripped
through the YAML writer, never reordered, never requoted. Only a missing `kind`
or `node` is added, and a `node` that points somewhere else is a person's
decision — it is counted and said out loud, never overwritten.
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

THEIRS = """---
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


def front(path: pathlib.Path) -> str:
    return cardfile.FRONT.match(path.read_text("utf-8"))["front"]


class APersonsFrontMatterIsNotTheCommandsToWrite(unittest.TestCase):
    def setUp(self):
        self.root = vault()
        note(self.root).parent.mkdir(parents=True)
        note(self.root).write_text(THEIRS, "utf-8")

    def test_the_properties_a_vault_queries_are_still_there_after_a_run(self):
        """The control: every one of these vanished before the fix."""
        remember.write_memory(self.root, log())
        kept = front(note(self.root))
        for line in ("tags:", "status: open", "priority: null",
                     "# the properties this vault queries, on every note"):
            self.assertIn(line, kept)

    def test_the_front_matter_is_the_same_text_it_was_after_two_runs(self):
        """Byte for byte, so nothing reorders it, requotes it or drops the
        comment — and the second run proves the first was already stable."""
        was = front(note(self.root))
        remember.write_memory(self.root, log())
        remember.write_memory(self.root, log())
        self.assertEqual(was, front(note(self.root)))


class OnlyAMissingKeyIsAdded(unittest.TestCase):
    def setUp(self):
        self.root = vault()
        note(self.root).parent.mkdir(parents=True)

    def test_a_note_missing_only_the_node_line_gains_exactly_that_line(self):
        note(self.root).write_text("---\ntags: [\"tempo\"]\nkind: memory\n---\n", "utf-8")
        remember.write_memory(self.root, log())
        self.assertEqual(['tags: ["tempo"]', "kind: memory", "node: '[[T30/01-schema]]'"],
                         front(note(self.root)).splitlines())
        completed = note(self.root).read_bytes()
        remember.write_memory(self.root, log())      # a completed note is stable too
        self.assertEqual(completed, note(self.root).read_bytes())

    def test_a_node_line_pointing_somewhere_else_leaves_the_whole_file_alone(self):
        """A person may have aimed it at a note that was renamed. Overwriting
        that is deciding for them; saying so is not — and a note whose `node`
        says it is about another card is not this command's to rebuild either
        (`test_remember_owns_only_what_it_marks` holds that whole case)."""
        note(self.root).write_text(
            '---\nkind: memory\nnode: "[[T30/01-schema-renamed]]"\n---\n', "utf-8")
        was = note(self.root).read_bytes()
        counts = remember.write_memory(self.root, log())
        self.assertEqual(was, note(self.root).read_bytes())
        self.assertEqual(1, counts["untouched"])

    def test_a_note_the_command_makes_itself_still_carries_both_keys(self):
        remember.write_memory(self.root, log())
        self.assertEqual(["kind: memory", "node: '[[T30/01-schema]]'"],
                         front(note(self.root)).splitlines())

    def test_a_note_with_no_front_matter_at_all_is_given_some(self):
        note(self.root).write_text("## 2026-09-21 — mine\n\nno front matter here.\n", "utf-8")
        remember.write_memory(self.root, log())
        text = note(self.root).read_text("utf-8")
        self.assertEqual(["kind: memory", "node: '[[T30/01-schema]]'"],
                         front(note(self.root)).splitlines())
        self.assertIn("no front matter here.", text)


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
