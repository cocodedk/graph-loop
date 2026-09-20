"""The command owns the sections whose heading carries its marker, and `kind`
and `node` when the front matter has neither. Every other byte is the person's.

An independent review found three ways the first version broke that promise: a
note whose `node` pointed at another card was rebuilt while the summary said it
had been left alone; prose before the first heading and anything a person added
under `## Node` were dropped, neither carrying the marker; and front matter
written in YAML flow style — `{kind: memory}` — had a line appended after the
closing brace, which is not the mapping and not YAML.
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

EXPECTED_TESTS = 8

AIMED = """---
kind: memory
node: "[[T30/01-schema-renamed]]"
---

## Node

- [[T30/01-schema-renamed]]

## 2026-09-01 — what this card was before it was renamed — from the log

2026-09-01T09:00:00Z. The plan phase added this card.
"""

PROSE = """---
kind: memory
node: "[[T30/01-schema]]"
---

This note is about the schema atom, and the field it is named after is the one
the producer writes. Read the two together.

## Node

- [[T30/01-schema]]
- [[T30/molecule]]

what I keep under here: the molecule is the piece this was cut from.
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
             "added": ["T30", "T30.schema"]},
            {"at": "2026-09-20T07:05:30Z", "kind": "step", "task": "T30.schema",
             "step": "gate", "seconds": 8.25, "passed": True, "code": 0}]


def note(root: pathlib.Path) -> pathlib.Path:
    return root / "T30" / "relatives" / "memory-01-schema.md"


def given(text: str) -> tuple[pathlib.Path, pathlib.Path]:
    root = vault()
    note(root).parent.mkdir(parents=True)
    note(root).write_text(text, "utf-8")
    return root, note(root)


class ANoteAimedAtAnotherNodeIsNotWrittenAtAll(unittest.TestCase):
    def test_not_one_byte_of_it_changes(self):
        """Counting a repointed note while rebuilding its history is worse
        than rebuilding it quietly: the summary then says the opposite."""
        root, path = given(AIMED)
        before = path.read_bytes()
        counts = remember.write_memory(root, log())
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(1, counts["untouched"])

    def test_the_summary_says_what_actually_happened(self):
        root, _ = given(AIMED)
        said = remember.write_memory(root, log())["said"]["T30.schema"]
        self.assertIn("[[T30/01-schema-renamed]]", said)
        self.assertIn("nothing here was changed", said)


class WhatCarriesNoMarkerIsNotTheCommandsToTouch(unittest.TestCase):
    def setUp(self):
        self.root, self.path = given(PROSE)
        remember.write_memory(self.root, log())
        self.text = self.path.read_text("utf-8")

    def test_prose_before_the_first_heading_survives(self):
        self.assertIn("This note is about the schema atom, and the field it is named "
                      "after is the one\nthe producer writes. Read the two together.",
                      self.text)

    def test_what_a_person_added_under_the_node_heading_survives(self):
        self.assertIn("- [[T30/molecule]]", self.text)
        self.assertIn("what I keep under here: the molecule is the piece this was cut "
                      "from.", self.text)

    def test_the_link_the_command_owns_is_still_there_and_not_doubled(self):
        self.assertEqual(1, self.text.count("- [[T30/01-schema]]"))

    def test_a_second_run_changes_no_byte(self):
        before = self.path.read_bytes()
        remember.write_memory(self.root, log())
        self.assertEqual(before, self.path.read_bytes())


class FlowStyleFrontMatterIsLeftAloneNotCorrupted(unittest.TestCase):
    def test_a_flow_mapping_keeps_its_own_text_and_still_parses(self):
        root, path = given("---\n{kind: memory, tags: [keep]}\n---\n")
        counts = remember.write_memory(root, log())
        front = cardfile.FRONT.match(path.read_text("utf-8"))["front"]
        self.assertEqual("{kind: memory, tags: [keep]}", front)
        self.assertEqual({"kind": "memory", "tags": ["keep"]}, yaml.safe_load(front))
        self.assertIn("flow style", counts["said"]["T30.schema"])

    def test_an_empty_flow_mapping_neither_raises_nor_becomes_nonsense(self):
        root, path = given("---\n{}\n---\n")
        remember.write_memory(root, log())
        front = cardfile.FRONT.match(path.read_text("utf-8"))["front"]
        self.assertEqual("{}", front)
        self.assertEqual({}, yaml.safe_load(front) or {})


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
