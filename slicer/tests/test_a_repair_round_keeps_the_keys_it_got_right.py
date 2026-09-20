"""A plan phase spent three rounds on the shape of its own answer.

Round 1 wrote `source` as a bare string; round 2 wrote it as a list but kept
the `repo/` prefix the prompt's own placeholder had shown it; round 3 spelled
the path right and dropped `needs`, a key it had written correctly in both
earlier rounds. Three planner calls, no card (2026-09-18).

Two faults, both here. The prompt said each anchor is a `repo/path:line`,
a template a model is free to read as a literal prefix — the same class as the
`path:text` placeholder fixed the same day. And the refusal fed back asks for
"one corrected answer" without saying that everything else stays as written, so
a planner correcting one key rewrites the whole answer from memory and loses
another.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import repair
from intelligence import Reply

import slicer

EXPECTED_TESTS = 3


def molecule() -> str:
    return yaml.safe_dump({
        "result": "MOLECULE", "reason": "one missing function", "molecule": {
            "name": "greeting", "source": ["specs/greeting.md:1"],
            "goal": "return a greeting", "why": "the function is absent", "needs": [],
            "atoms": [], "files": ["app.py"], "gate": "set -e -o pipefail\nfalse",
            "done_when": "the greeting test passes", "may_add_files": True}},
        sort_keys=False)


class TheAnchorExampleIsAPathNotATemplate(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.repo = self.root / "repo"
        self.specs = self.repo / "specs"
        self.specs.mkdir(parents=True)
        self.source = self.specs / "greeting.md"
        self.source.write_text("## Goal\nReturn a greeting.\n", "utf-8")

    def test_the_prompt_shows_a_real_relative_path(self):
        said = slicer.prompt(self.repo, [self.source], [])
        self.assertNotIn("repo/path:line", said)
        self.assertIn("specs/greeting.md:1", said)     # spelled as the approved sources are


class TheRefusalSaysToKeepWhatWasRight(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.repo = self.root / "repo"
        self.backlog, self.specs = self.repo / "backlog", self.repo / "specs"
        self.backlog.mkdir(parents=True)
        self.specs.mkdir()
        (self.specs / "greeting.md").write_text("## Goal\nReturn a greeting.\n", "utf-8")

    def test_the_repair_round_says_so(self):
        asked: list[str] = []

        def ask_once(question: str) -> str:
            asked.append(question)
            return "answer"

        def write(_: str) -> tuple[str, object]:
            if len(asked) < 2:
                raise ValueError("source must be a list of strings")
            return "published", "done"

        repair.repaired("plan it", ask_once, write)
        self.assertIn("Change only what was refused", asked[1])

    def test_the_slicer_command_says_so(self):
        replies = [Reply(True, "{}"), Reply(True, molecule())]
        with mock.patch.object(slicer, "ask", side_effect=replies) as ask:
            slicer.main(["--repo", str(self.repo), "--backlog", str(self.backlog),
                         "--source", "specs"])
        self.assertIn("Change only what was refused", ask.call_args.args[0])


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
