"""A file grant is a path. A `path:text` name in `files` cannot be built.

The builder writes the file the card exists to create, and the file fence
compares that bare path against the card's grant. A grant of
`src/main/java/link/PostLink.java:parsePostId` never matches the path the
builder wrote, so the one file the card is for is the one file the fence
forbids. Every card with a grant in the third campaign carried it — nine of
nine — and both cards that reached a builder failed with "the builder wrote
outside its files" naming their own file (2026-09-18).

The validator had no opinion: `_inside` asks whether a path stays in the
repository, and a colon is legal in a POSIX filename, so a name passed as a
path. `uses` and `creates` are the only fields where `path:text` is a name,
and the prompt now says so where it says what `files` is.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from contracts import validate

import slicer

EXPECTED_TESTS = 4


class AFileGrantIsAPath(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        (self.repo / "specs").mkdir()
        (self.repo / "specs" / "greeting.md").write_text("# Greeting\nIt is returned.\n", "utf-8")
        (self.repo / "app.py").write_text("def read():\n    return 1\n", "utf-8")

    def answer(self, **more: object) -> dict:
        made = {"name": "greeting", "source": ["specs/greeting.md:2"],
                "goal": "return a greeting", "why": "the function is absent", "needs": [],
                "atoms": [], "files": ["app.py"], "gate": "set -e -o pipefail\nfalse",
                "done_when": "the greeting test passes"}
        made.update(more)
        return {"result": "MOLECULE", "reason": "one gap", "molecule": made}

    def check(self, answered: dict) -> dict:
        return validate(answered, repo=self.repo, sources=[self.repo / "specs"], rows=[])

    def test_a_name_in_files_is_refused(self):
        # `may_add_files` is what the real cards carried — they exist to create
        # the file — and it is what let the name past `available`, whose "does
        # this path exist" refusal would otherwise have caught it by accident.
        with self.assertRaisesRegex(ValueError, r"files.*app\.py:read"):
            self.check(self.answer(files=["app.py:read"], may_add_files=True))

    def test_the_refusal_says_where_the_name_belongs(self):
        try:
            self.check(self.answer(files=["app.py:read"], may_add_files=True))
        except ValueError as refused:
            said = str(refused)
        self.assertIn("app.py", said)          # the bare path to write instead
        self.assertIn("uses", said)            # and where a name goes

    def test_a_name_is_still_a_name_in_uses(self):
        # The fix must not reach the two fields where `path:text` is correct.
        self.check(self.answer(uses=["app.py:read"]))

    def test_the_prompt_says_a_file_is_a_bare_path(self):
        said = slicer.prompt(self.repo, [self.repo / "specs" / "greeting.md"], [])
        self.assertIn("files is a bare repository path", said)


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
