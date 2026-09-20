"""The planner tries every account, as the builders do.

It named one. When that account's session expired, every replan in the
campaign crashed with "OAuth session expired" while the other account was
answering normally.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import resources
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import turn
import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from backlog import Backlog
from providers import Outcome
from workspace import Workspace

BELT = resources.belt('plan')

EXPECTED_TESTS = 4

CONTRACT = '{"goal": "a better goal", "files": ["a.py"], "done_when": "it holds"}'


class ThePlannerWalksTheAccounts(unittest.TestCase):
    def replanning(self, answers):
        """One refused card, one planner that answers per account as told."""
        seen = []

        def planner(_prompt, resource):
            seen.append(resource)
            return answers(resource)

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "backlog.yaml").write_text(yaml.safe_dump({"tasks": [
                {"id": "T1", "status": "refused_contract", "needs": [], "replans": 0,
                 "files": ["a.py"], "gate": "true", "goal": "g", "done_when": "d",
                 "refused_why": "because"}]}))
            space = Workspace(root)
            turn.replan_pending(Backlog(root / "backlog.yaml"), space, planner)
            calls = [row for row in space.events()
                     if row.get("kind") == "step" and row.get("step") == "replan_call"]
            attempts = [row for row in space.events() if row.get("kind") == "attempt"]
        return seen, calls, attempts

    def test_the_belt_is_walked_when_a_resource_refuses_before_reading(self):
        """An expired session belongs to the ACCOUNT, so the belt skips that
        account's other models and tries the next account."""
        seen, calls, attempts = self.replanning(
            lambda resource: Outcome("ok", text=CONTRACT) if resource == BELT[-1]
            else Outcome("auth", text="expired", cost=0, tokens=0))
        first_of_each = [r for i, r in enumerate(BELT)
                         if r.account not in {x.account for x in BELT[:i]}]
        self.assertEqual(seen, first_of_each, "the belt did not skip the spent account")
        self.assertEqual(len(calls), len(seen), "a call on the belt left no record")
        self.assertEqual([row.get("on") for row in calls], [str(r) for r in seen])
        self.assertEqual(len(attempts), len(seen), "one attempt hid the others")
        self.assertEqual({row.get("account") for row in attempts}, {"plan"},
                         "an attempt filed under a real account counts as unkept builder work")

    def test_the_first_account_answering_is_the_only_call(self):
        seen, calls, _ = self.replanning(lambda resource: Outcome("ok", text=CONTRACT))
        self.assertEqual(seen, [BELT[0]])
        self.assertEqual(len(calls), 1)

    def test_the_replan_step_is_not_nested_inside_a_second_step(self):
        """`replan_call` times the one real unit of work — one planner call on
        one resource. A second, wider "replan" step used to wrap it, so the
        same seconds landed in report.py's clock, by_step and by_task totals
        twice. One call must leave exactly one `step` event."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "backlog.yaml").write_text(yaml.safe_dump({"tasks": [
                {"id": "T1", "status": "refused_contract", "needs": [], "replans": 0,
                 "files": ["a.py"], "gate": "true", "goal": "g", "done_when": "d",
                 "refused_why": "because"}]}))
            space = Workspace(root)
            turn.replan_pending(Backlog(root / "backlog.yaml"), space,
                                lambda _prompt, resource: Outcome("ok", text=CONTRACT))
            steps = [row.get("step") for row in space.events() if row.get("kind") == "step"]
        self.assertEqual(steps, ["replan_call"], "the wrapping step double-counted its own call")

    def test_every_call_of_every_round_is_recorded(self):
        seen, calls, _ = self.replanning(lambda resource: Outcome("auth", text="expired", cost=0, tokens=0))
        accounts = {r.account for r in BELT}
        self.assertEqual(len(accounts), len({r.account for r in seen[:len(accounts)]}))
        self.assertEqual(len(calls), len(seen), "a planner call left no record")


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
