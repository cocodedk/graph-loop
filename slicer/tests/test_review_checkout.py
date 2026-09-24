"""A slicer review reads the checkout the planner read, never the driver's own.

astra's review, finding 21: neither review passed `cwd`, so `codex exec` ran
without `--cd` and read whatever directory the process happened to sit in —
the driver's working tree, not the clean checkout of the campaign tip the
slicer plans against (`slice_turn` cuts it and passes it as `--repo`).
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import intelligence
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from tree import publish

import slicer

EXPECTED_TESTS = 2


def molecule(**changes) -> dict:
    body = {"name": "greeting", "source": ["specs/greeting.md:1"],
            "goal": "return a greeting", "why": "the function is absent", "needs": [],
            "atoms": [], "files": ["app.py"], "gate": "set -e -o pipefail\nfalse",
            "done_when": "the greeting test passes", "may_add_files": True}
    body.update(changes)
    return {"result": "MOLECULE", "reason": "one missing function", "molecule": body}


class ReviewCheckoutTest(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp()) / "clean"
        self.backlog, self.specs = self.repo / "backlog", self.repo / "specs"
        self.backlog.mkdir(parents=True)
        self.specs.mkdir()
        self.source = self.specs / "greeting.md"
        self.source.write_text("## Goal\nReturn a greeting.\n", "utf-8")
        self.seen: dict = {}

        def fake_codex(binary, prompt, **passed):
            self.seen.update(passed, prompt=prompt)
            return types.SimpleNamespace(ok=True, verdict="ACCEPT", text="fine", kind="ok")

        self.codex = mock.patch.object(intelligence.providers, "codex", fake_codex)

    def test_the_progress_review_runs_in_the_checkout_the_planner_read(self):
        publish(self.backlog, molecule(name="large")["molecule"])
        slicer.Backlog(self.backlog).set_status("large", "needs_slice",
                                                refused_why="the gate is too broad", triage="work")
        child = molecule(name="smaller", goal="narrow greeting")
        with self.codex:
            state, _detail = slicer.run_answer(yaml.safe_dump(child), repo=self.repo,
                                               backlog=self.backlog, sources=[self.specs],
                                               target_id="large")
        self.assertEqual("published", state)
        self.assertEqual(str(self.repo), self.seen.get("cwd"))

    def test_the_coverage_review_runs_in_that_checkout_and_is_told_where_it_is(self):
        answer = yaml.safe_dump({"result": "NO_GAP", "reason": "nothing left", "molecule": None})
        with self.codex:
            state, _detail = slicer.run_answer(answer, repo=self.repo, backlog=self.backlog,
                                               sources=[self.source])
        self.assertEqual("covered", state)
        self.assertEqual(str(self.repo), self.seen.get("cwd"))
        self.assertIn(f"Repository to inspect: {self.repo}", self.seen.get("prompt", ""))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
