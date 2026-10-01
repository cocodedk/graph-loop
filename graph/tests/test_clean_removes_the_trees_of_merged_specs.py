"""`lean_clean.py` removes the trees of merged specs and nothing else (issue #259).

Runs left /tmp/graph-* and /tmp/lean-build-* trees behind until they filled a per-user quota, and a cleanup
by directory age once deleted a live run's tree. A tree is named by the workspace's own event log and is
removed only when its spec is built on origin/main, whatever its age.
"""

import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean
import lean_clean
import lean_run
import project_specs
import tmp_root  # noqa: F401
from workspace import Workspace

EXPECTED_TESTS = 4


def tree(prefix):
    """A tree the way a run makes it: inside its own mkdtemp folder."""
    parent = pathlib.Path(tempfile.mkdtemp(prefix=prefix))
    (parent / "task-build").mkdir()
    (parent / "task-build" / "app.bin").write_text("x")
    return parent / "task-build"


class Clean(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace(tempfile.mkdtemp())

    def run_clean(self, built):
        with mock.patch.object(project_specs, "built_names", return_value=set(built)):
            return lean_clean.main(["--workspace", str(self.ws.root), "--repo", "repo"])

    def test_the_trees_of_a_merged_spec_go_and_an_unmerged_specs_stay(self):
        merged, kept, built = tree("graph-"), tree("graph-"), tree("lean-build-")
        self.ws.event("lean_feature_started", task="01-merged", tree=str(merged))
        self.ws.event("lean_feature_started", task="02-open", tree=str(kept))
        self.ws.event("lean_built", task="01-merged", tree=str(built))
        self.assertEqual(0, self.run_clean({"01-merged"}))
        self.assertEqual([False, False, True], [merged.exists(), built.exists(), kept.exists()])
        self.assertFalse(merged.parent.exists())          # the mkdtemp folder goes with it

    def test_a_tree_that_will_not_go_is_reported_and_kept(self):
        stuck = tree("graph-")
        self.ws.event("lean_tree_left", task="01-merged", tree=str(stuck))
        with mock.patch.object(lean_clean.shutil, "rmtree", side_effect=OSError("root-owned")), \
                mock.patch("builtins.print") as said:
            self.run_clean({"01-merged"})
        self.assertTrue(stuck.exists())
        self.assertIn(f"left: {stuck}", [call.args[0] for call in said.call_args_list])

    def test_a_tree_already_gone_is_no_error(self):
        self.ws.event("lean_feature_started", task="01-merged", tree="/nonexistent/at/all")
        self.assertEqual(0, self.run_clean({"01-merged"}))


class Built(unittest.TestCase):
    def test_the_build_event_names_its_task_and_tree(self):
        ws = Workspace(tempfile.mkdtemp())
        folder = pathlib.Path(tempfile.mkdtemp())
        made = types.SimpleNamespace(path=str(folder), commit="abc")
        profile = {"build_command": "build-it", "artifact": "app.bin"}
        with mock.patch.object(lean, "Worktree") as worktree, \
                mock.patch.object(lean_run, "masked", return_value=(True, "")), \
                mock.patch.object(lean_run, "mail"):
            worktree.return_value.create.return_value = made
            lean.finish(ws, "repo", profile, "01-x", "https://example.test/pull/1")
        row = next(r for r in ws.events() if r["kind"] == "lean_built")
        self.assertEqual(("01-x", str(folder)), (row["task"], row["tree"]))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())   # the four above and this one


if __name__ == "__main__":
    unittest.main()
