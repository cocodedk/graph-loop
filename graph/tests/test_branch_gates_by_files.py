"""A keep checks its own contract and completed work whose files overlap."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import loop_judge
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from backlog import Backlog
from doctor import check_backlog

EXPECTED_TESTS = 4


def _loop(rows: list[dict]):
    path = pathlib.Path(tempfile.mkdtemp()) / "b.yaml"
    path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": rows},
                                   sort_keys=False))

    class Loop:
        backlog = Backlog(path)

    return Loop()


class TouchedFilesTest(unittest.TestCase):
    def test_kept_one_shot_gates_use_only_the_explicit_lasting_form(self):
        lasting = "grep -q implemented a.py"
        judge = {"id": "J", "status": "done", "files": ["a.py"],
                 "gate": "! grep -q implemented a.py", "gate_until_kept": True,
                 "gate_when_kept": lasting}
        current = {"id": "C", "status": "todo", "files": ["a.py"],
                   "gate": "test -f a.py", "gate_until_kept": True,
                   "gate_when_kept": "false"}
        loop = _loop([judge, current])
        self.assertEqual([], check_backlog(loop.backlog))
        self.assertEqual([lasting, current["gate"]],
                         loop_judge._gates_on_the_branch(loop, current))
        self.assertEqual("J", loop_judge._gate_owner(loop, current, lasting))

    def test_one_shot_cards_without_a_lasting_gate_draw_one_named_complaint(self):
        for status in ("todo", "done", "dropped", "sliced", "rejected"):
            for fields in ({}, {"gate_when_kept": None}, {"gate_when_kept": ""},
                           {"gate_when_kept": " \t\n"}):
                with self.subTest(status=status, fields=fields):
                    judge = {"id": "J", "status": status, "files": ["a.py"],
                             "gate": "test -f a.py", "gate_until_kept": True, **fields}
                    complaints = check_backlog(_loop([judge]).backlog)
                    self.assertEqual(1, len(complaints))
                    self.assertEqual("J", complaints[0].about)
                    self.assertIn("gate_when_kept", complaints[0].do)

    def test_only_affected_cards_are_gated_regardless_of_age(self):
        rows: list[dict] = [
            {"id": f"K{n}", "goal": "g", "status": "done", "gate": f"test -f k{n}",
             "files": [f"k{n}"], "needs": [], "kept_at": f"2026-08-30T{10 + n}:00:00Z"}
            for n in range(8)]
        rows.append({"id": "NOW", "goal": "g", "status": "todo", "gate": "test -f now",
                     "files": ["k1"], "needs": []})  # and this card edits K1's own file
        gates = loop_judge._gates_on_the_branch(_loop(rows), rows[-1])
        # Retires the last-six policy: only affected work.
        self.assertEqual(["test -f k1", "test -f now"], gates)


    def test_a_recent_unrelated_failure_cannot_block_a_keep(self):
        from keep import Keeper
        from test_keep import repo
        from worktree import Worktree

        root = repo()
        keeper = Keeper(root, "campaign/test")
        tree = Worktree(root, "NOW", keeper.tip()).create()
        (pathlib.Path(tree.path) / "a.py").write_text("changed\n")
        rows = [
            {"id": "OLD", "goal": "g", "status": "done", "files": ["other.py"],
             "gate": "false", "needs": []},
            {"id": "NOW", "goal": "g", "status": "todo", "files": ["a.py"],
             "gate": "test -f a.py", "needs": []}]
        gates = loop_judge._gates_on_the_branch(_loop(rows), rows[-1])
        commit = keeper.keep("NOW", tree.path, "change a", files=["a.py"], gates=gates)
        self.assertTrue(commit)
        self.assertEqual(commit, keeper.tip())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
