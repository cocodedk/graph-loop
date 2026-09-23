"""One goal reaches the unchanged graph picker through the speccer and slicer."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]

SLICER = pathlib.Path(__file__).resolve().parents[1]
GRAPH = SLICER.parent / "graph" / "graph-goal.py"
sys.path.insert(0, str(SLICER))
from intelligence import Reply
from speccer import write_answer

from slicer import run_answer

EXPECTED_TESTS = 1


class Vertical(unittest.TestCase):
    def test_goal_spec_molecule_atom_and_unchanged_picker_fit(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        specs, backlog, campaign = repo / "specs", repo / "backlog", repo / "campaign"
        backlog.mkdir()
        specced = yaml.safe_dump({
            "result": "SPEC", "reason": "one small goal", "spec": {
                "name": "greeting", "body": (
                    "## Goal\nReturn a greeting.\n\n## Acceptance\nThe greeting test passes.\n\n"
                    "## Boundaries\nNo network or live action.\n")}}, sort_keys=False)
        state, source = write_answer(
            specced, goal="return a greeting", spec_root=specs,
            reviewer=lambda question: Reply(True, "accepted"))
        self.assertEqual("written", state)
        sliced = yaml.safe_dump({
            "result": "MOLECULE", "reason": "the function is absent", "molecule": {
                "name": "greeting", "source": ["specs/greeting.md:1"],
                "goal": "return one greeting", "why": "the function is absent",
                "needs": [], "atoms": [], "files": ["app.py"],
                "gate": "set -e -o pipefail\nfalse",
                "done_when": "the greeting test passes", "may_add_files": True}},
            sort_keys=False)
        self.assertEqual(("published", "greeting"), run_answer(
            sliced, repo=repo, backlog=backlog, sources=[pathlib.Path(source)]))
        env = {**os.environ, "GRAPH_REPO": str(repo), "GRAPH_BACKLOG": str(backlog),
               "GRAPH_CAMPAIGN": str(campaign), "GRAPH_BRANCH": "campaign/fictive"}
        subprocess.run([sys.executable, str(GRAPH), "init", "--backlog", str(backlog)],
                       env=env, check=True, capture_output=True, text=True)
        subprocess.run([sys.executable, str(GRAPH), "approve"], env=env, check=True,
                       capture_output=True, text=True)
        (campaign / "contact").write_text("person@example.test\n")
        done = subprocess.run([sys.executable, str(GRAPH), "run", "--dry-run"], env=env,
                              check=True, capture_output=True, text=True)
        self.assertIn("would run greeting: return one greeting", done.stdout)


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
