"""Two lanes can each pass alone and be red together: the gate runs once more on
the tree about to be published. Split from `test_keep` at the 200-line cap."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from keep import CombinedGateFailed, Keeper
from test_keep import repo, sha

EXPECTED_TESTS = 10


class CombinedGateTest(unittest.TestCase):
    """Two lanes can each pass alone and be red together; the branch is what a
    person reads, so the gate runs once more on the tree about to be published."""

    def setUp(self):
        self.root = repo()
        self.keeper = Keeper(self.root, "campaign/test")

    def _tree(self, task_id: str, name: str, text: str) -> str:
        path = str(pathlib.Path(tempfile.mkdtemp()) / task_id)
        subprocess.run(("git", "-C", self.root, "worktree", "add", "-q", "--detach",
                        path, self.keeper.tip()), capture_output=True, check=True)
        (pathlib.Path(path) / name).write_text(text)
        return path

    def test_a_combined_failure_names_the_gate_and_its_last_words(self):
        # a mute combined failure consumed T4.close's last two rounds telling nobody why
        tree = self._tree("T9", "i.py", "nine\n")
        with self.assertRaises(CombinedGateFailed) as caught:
            self.keeper.keep("T9", tree, "ninth", files=["i.py"],
                             gates=["cat i.py >&2; false"])
        # 'nine' lives only in the FILE the gate read: its presence proves the
        # gate's OUTPUT travelled, not merely the gate's own text
        self.assertIn("cat i.py", str(caught.exception))
        self.assertIn("nine", str(caught.exception))
        with self.assertRaises(CombinedGateFailed) as mute:
            self.keeper.keep("T9", tree, "ninth", files=["i.py"], gates=["false"])
        self.assertIn("printed nothing", str(mute.exception))

    def test_a_combination_that_fails_the_gate_is_not_published(self):
        first = self._tree("T1", "a.py", "changed\n")   # the fixture already holds "one"
        self.keeper.keep("T1", first, "first", files=["a.py"])
        tip = sha(self.root, "campaign/test")
        second = self._tree("T2", "b.py", "two\n")
        with self.assertRaises(CombinedGateFailed):
            self.keeper.keep("T2", second, "second", files=["b.py"], gates=["test ! -f a.py"])
        self.assertEqual(tip, sha(self.root, "campaign/test"))   # the branch did not move

    def test_a_combination_that_passes_is_published(self):
        third = self._tree("T3", "c.py", "three\n")
        commit = self.keeper.keep("T3", third, "third", files=["c.py"], gates=["test -f c.py"])
        self.assertTrue(commit)


    def test_a_failing_gate_is_not_masked_by_the_next_one(self):
        # Joined with && into one shell, `false; true` would have swallowed the
        # failure and published a red branch. Each gate runs in its own shell.
        seventh = self._tree("T7", "g.py", "seven\n")
        with self.assertRaises(CombinedGateFailed):
            self.keeper.keep("T7", seventh, "seventh", files=["g.py"],
                             gates=["test -f nothing-here", "test -f g.py; true"])

    def test_a_rebuilt_candidate_is_gated_too(self):
        # The branch moved under this keep; the retry must gate the new combination.
        seen = []
        first = self._tree("T4", "d.py", "four\n")
        original = self.keeper._combined_tree_red
        self.keeper._combined_tree_red = lambda task_id, commit, gates: (
            seen.append(commit) or original(task_id, commit, gates))
        self.keeper.keep("T4", first, "fourth", files=["d.py"], gates=["test -f d.py"])
        self.assertEqual(1, len(seen))
        self.keeper._combined_tree_red = original

    def test_a_checkout_that_cannot_be_made_is_not_a_pass(self):
        self._tree("T5", "e.py", "five\n")
        with self.assertRaises(RuntimeError):
            self.keeper._combined_tree_red("T5", "0" * 40, ["true"])   # no such commit


    def test_the_candidate_checkout_carries_the_runtime_material(self):
        # A gate that needs the minted secrets must not fail for want of them.
        # Which material that is belongs to the repository, so it is named.
        (pathlib.Path(self.root) / "runtime").mkdir(exist_ok=True)
        (pathlib.Path(self.root) / "runtime" / ".env").write_text("TOKEN=x\n")
        sixth = self._tree("T6", "f.py", "six\n")
        with mock.patch.dict(os.environ, {"DRIVE_PROVISION_COPY": "runtime"}):
            commit = self.keeper.keep("T6", sixth, "sixth", files=["f.py"],
                                      gates=["test -f runtime/.env"])
        self.assertTrue(commit)


class StaleCandidateTest(unittest.TestCase):
    def test_a_candidate_built_on_a_moved_tip_is_rebuilt_not_blamed(self):
        root = repo()
        keeper = Keeper(root, "campaign/test")
        def tree(name, text, task):
            path = str(pathlib.Path(tempfile.mkdtemp()) / task)
            subprocess.run(("git", "-C", root, "worktree", "add", "-q", "--detach", path, keeper.tip()),
                           capture_output=True, check=True)
            (pathlib.Path(path) / name).write_text(text)
            return path
        mine = tree("i.py", "nine\n", "T9")
        rounds = []
        def sibling_lands():
            if not rounds:                      # once, between the build and the gate
                rounds.append(1)
                other = tree("j.py", "ten\n", "T10")
                keeper.keep("T10", other, "tenth", files=["j.py"])
            return ["test -f i.py"]
        commit = keeper.keep("T9", mine, "ninth", files=["i.py"], gates=sibling_lands)
        self.assertTrue(commit)                 # rebuilt on the new tip and published


class BeforePublishTest(unittest.TestCase):
    def test_the_card_is_recorded_when_the_branch_holds_it(self):
        root = repo()
        keeper = Keeper(root, "campaign/test")
        path = str(pathlib.Path(tempfile.mkdtemp()) / "T8")
        subprocess.run(("git", "-C", root, "worktree", "add", "-q", "--detach", path, keeper.tip()),
                       capture_output=True, check=True)
        (pathlib.Path(path) / "h.py").write_text("eight\n")
        seen = []
        keeper.keep("T8", path, "eighth", files=["h.py"],
                    record=lambda sha: seen.append(
                        subprocess.run(("git", "-C", root, "rev-parse", "-q", "--verify", "campaign/test"),
                                       capture_output=True, text=True, check=False).stdout.strip()))
        # Recorded only once the branch really holds the commit: a crash between
        # the two must never leave the backlog claiming work the branch lacks.
        self.assertEqual(1, len(seen))
        self.assertTrue(seen[0])


class BranchGatesTest(unittest.TestCase):
    def test_the_affected_kept_cards_gates_are_checked_too(self):
        # A lane that passes alone must not break work that landed before it.
        import tempfile as tf

        import loop_judge
        import yaml as y  # type: ignore[import-untyped]  # no stubs in this environment
        from backlog import Backlog
        rows = [{"id": "T1", "goal": "g", "status": "done", "gate": "test -f a.py", "files": ["a.py"], "needs": []},
                {"id": "T2", "goal": "g", "status": "done", "gate": "true", "files": ["b.py"], "needs": [],
                 "gate_has_side_effects": True},                       # live: never re-run
                {"id": "T3", "goal": "g", "status": "todo", "gate": "test -f c.py", "files": ["a.py", "b.py", "c.py"], "needs": []}]
        rows[0]["kept_at"] = "2026-08-30T10:00:00Z"
        path = pathlib.Path(tf.mkdtemp()) / "b.yaml"
        path.write_text(y.safe_dump({"schema": "e2e-backlog.v1", "tasks": rows}, sort_keys=False))
        class Loop:
            backlog = Backlog(path)
        gates = loop_judge._gates_on_the_branch(Loop(), rows[2])
        self.assertEqual(["test -f a.py", "test -f c.py"], gates)      # the live one is out
        self.assertEqual("test -f c.py", gates[-1])                    # this card's gate, always last
        self.assertEqual([], loop_judge._gates_on_the_branch(Loop(), rows[1]))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
