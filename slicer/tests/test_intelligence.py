"""The planning belt gets read tools and no inherited MCP authority."""

from __future__ import annotations

import pathlib
import sys
import types
import unittest
import unittest.mock

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from intelligence import _argv

EXPECTED_TESTS = 3


class Boundary(unittest.TestCase):
    def test_the_planner_command_is_read_only_and_medium(self):
        resource = types.SimpleNamespace(model="claude-opus-5")
        command = _argv(resource)
        self.assertIn("--strict-mcp-config", command)
        self.assertEqual("Read,Grep,Glob", command[command.index("--tools") + 1])
        self.assertEqual("Read,Grep,Glob", command[command.index("--allowedTools") + 1])
        denied = command[command.index("--disallowedTools") + 1]
        for name in ("Agent", "Bash", "Edit", "Write", "MultiEdit", "Task", "WebFetch"):
            self.assertIn(name, denied)
        self.assertEqual("medium", command[command.index("--effort") + 1])


class CampaignRecords(unittest.TestCase):
    def test_a_refusal_then_a_success_records_both_calls_whole(self):
        import json
        import tempfile
        import types as _t

        import intelligence
        sys.path.insert(0, str(HERE.parents[0] / "graph" / "lib"))
        from workspace import Workspace  # type: ignore[import-not-found]
        space = Workspace(tempfile.mkdtemp()).init(goal="t", backlog="x")
        belt = [_t.SimpleNamespace(model="m1", account="work", agent="claude"),
                _t.SimpleNamespace(model="m2", account="second", agent="claude")]
        answers = [
            _t.SimpleNamespace(returncode=1, stdout="", stderr="Claude usage limit reached"),
            _t.SimpleNamespace(returncode=0, stderr="",
                               stdout=json.dumps({"result": "result: NO_GAP"}))]
        import os
        with unittest.mock.patch.dict(os.environ, {"GRAPH_ACCOUNTS": "work,second=/cfg/second"}), \
             unittest.mock.patch.object(intelligence, "CAMPAIGN", pathlib.Path(space.root)), \
             unittest.mock.patch.object(intelligence.resources, "belt", return_value=belt):
            reply = intelligence.ask("plan this", pathlib.Path("."),
                                     runner=lambda *a, **k: answers.pop(0))
        self.assertTrue(reply.ok)
        steps = [e for e in space.events() if e.get("kind") == "step"
                 and e.get("step") == "plan"]
        self.assertEqual(["work", "second"], [e.get("account") for e in steps])
        made = sorted(f.name for f in (pathlib.Path(space.root) / "calls"
                                       / "the slicer").iterdir())
        self.assertEqual(2, sum("plan-prompt" in n for n in made))
        self.assertEqual(2, sum("plan-answer" in n for n in made))


class ReviewRecords(unittest.TestCase):
    def test_a_review_call_records_its_step_through_the_real_workspace(self):
        import tempfile

        import intelligence
        sys.path.insert(0, str(HERE.parents[0] / "graph" / "lib"))
        from workspace import Workspace  # type: ignore[import-not-found]
        space = Workspace(tempfile.mkdtemp()).init(goal="t", backlog="x")

        def fake_codex(binary, prompt, *, cwd="", effort="", attempt=None):
            attempt("ok", "work", 0.01, 100, "REVIEW: ACCEPT")
            return types.SimpleNamespace(ok=True, verdict="ACCEPT", text="fine", kind="ok")

        with unittest.mock.patch.object(intelligence, "CAMPAIGN", pathlib.Path(space.root)), \
             unittest.mock.patch.object(intelligence.providers, "codex", fake_codex):
            reply = intelligence.review("review this", pathlib.Path(space.root))
        self.assertTrue(reply.ok)
        steps = [e for e in space.events() if e.get("kind") == "step"
                 and e.get("step") == "review"]
        self.assertEqual(1, len(steps))
        self.assertEqual("the slicer", steps[0]["task"])
        self.assertEqual("ok", steps[0]["outcome"])


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
