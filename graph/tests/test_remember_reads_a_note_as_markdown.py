"""A `## ` line inside code is an example, not a heading.

A second independent review found the command eating its own documentation: a
person showing what a generated section looks like, inside a fenced block, had
that example read as a heading carrying the ownership marker — so the command
took the example over as its own and everything after it went with the refresh.

A fence is ``` or ~~~, three or more, indented up to three spaces, with or
without an info string, and it closes on the same character at least as long
with no info string of its own. Inside one, nothing is a heading: not for
ownership, not for splitting sections, not for finding the link under `## Node`.

An INDENTED code block needs no rule of its own: a heading is a `## ` at column
zero, and every line of an indented block carries at least four spaces, so an
example written that way is already safe. There is a test for it here, because
that is an argument until something checks it.

A fence a person never closed is the one case this cannot read: there is no
telling where their text ends, the sections after it would be swallowed and
re-emitted, and the note would grow on every run. It is left alone and said.
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

EXPECTED_TESTS = 7

EXAMPLE = """## 2026-09-21 — how this note is written

A section the command owns looks like this:

```markdown
## 2026-09-20 — the gate ran, exit 1 — from the log

2026-09-20T07:05:30Z. Exit 1 after 42.7 seconds.
```

and one of mine looks like this one. Keep both."""

TILDE = """## 2026-09-21 — the same, fenced the other way

~~~~
## 2026-09-20 — planned — from the log
~~~~

still mine."""

INDENTED = """## 2026-09-21 — an example indented instead of fenced

    ## 2026-09-20 — planned — from the log

still mine."""


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


def given(section: str) -> tuple[pathlib.Path, pathlib.Path]:
    """A note the command has already written, with this section added by hand."""
    root = vault()
    remember.write_memory(root, log())
    path = note(root)
    path.write_text(path.read_text("utf-8").rstrip("\n") + "\n\n" + section + "\n", "utf-8")
    return root, path


class AnExampleInsideCodeIsNotASection(unittest.TestCase):
    def test_a_fenced_example_carrying_the_marker_survives_whole(self):
        root, path = given(EXAMPLE)
        remember.write_memory(root, grown())
        self.assertIn(EXAMPLE, path.read_text("utf-8"))

    def test_it_is_still_whole_after_a_second_run(self):
        root, path = given(EXAMPLE)
        remember.write_memory(root, grown())
        before = path.read_bytes()
        remember.write_memory(root, grown())
        self.assertEqual(before, path.read_bytes())

    def test_a_tilde_fence_is_a_fence_too(self):
        root, path = given(TILDE)
        remember.write_memory(root, grown())
        self.assertIn(TILDE, path.read_text("utf-8"))

    def test_an_indented_example_survives_because_a_heading_is_at_column_zero(self):
        root, path = given(INDENTED)
        remember.write_memory(root, grown())
        self.assertIn(INDENTED, path.read_text("utf-8"))


class TheLinkUnderNodeIsAskedOfRealLinesOnly(unittest.TestCase):
    def test_a_link_shown_inside_a_fence_does_not_stand_in_for_the_real_one(self):
        root = vault()
        note(root).parent.mkdir(parents=True)
        note(root).write_text(
            "---\nkind: memory\nnode: \"[[T30/01-schema]]\"\n---\n\n## Node\n\n"
            "the link is written like this:\n\n```\n- [[T30/01-schema]]\n```\n", "utf-8")
        remember.write_memory(root, log())
        text = note(root).read_text("utf-8")
        self.assertEqual(2, text.count("- [[T30/01-schema]]"), "the real one was added")


class AFenceNobodyClosedIsNotReadAtAll(unittest.TestCase):
    def setUp(self):
        self.root, self.path = given("## 2026-09-21 — mine\n\n```\nnever closed")
        self.before = self.path.read_bytes()
        self.counts = remember.write_memory(self.root, grown())

    def test_the_note_is_left_exactly_as_it_is(self):
        self.assertEqual(self.before, self.path.read_bytes())
        self.assertEqual(1, self.counts["untouched"])

    def test_the_summary_says_why(self):
        self.assertIn("fence", self.counts["said"]["T30.schema"])


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
