"""A person's answer releases a parked card for a fresh contract."""

import importlib.util
import pathlib
import sys
import tempfile
import unittest

import yaml

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import tmp_root  # noqa: F401 — isolate test files and locks

sys.path.insert(0, str(HERE / "lib"))
from backlog import Backlog
from workspace import Workspace

_spec = importlib.util.spec_from_file_location("graph_goal_answer", HERE / "graph-goal.py")
graph_goal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(graph_goal)


class AnswerCommandTest(unittest.TestCase):
    def test_answer_clears_hold_and_frozen_contract_and_carries_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = root / "backlog.yaml"
            path.write_text(yaml.safe_dump({"tasks": [{
                "id": "T1", "status": "todo", "blocked_by_human": True,
                "held_by": "owner", "accepted_criteria": {"gate": "old gate"},
                "contract_seen": True, "refused_why": "old complaint",
            }]}), encoding="utf-8")
            space = Workspace(root / "campaign").init(goal="g", backlog=str(path))
            decision = "Replace the gate with an XML-report gate."
            self.assertEqual(0, graph_goal.main([
                "--workspace", str(space.root), "answer", "T1", decision]))
            row = Backlog(path).task("T1")
            self.assertEqual("refused_contract", row["status"])
            self.assertEqual(decision, row["refused_why"])
            for field in ("blocked_by_human", "held_by", "accepted_criteria", "contract_seen"):
                self.assertNotIn(field, row)


if __name__ == "__main__":
    unittest.main()
