"""The campaign declares paths; the box keeps precisely those paths."""

import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import gate_paths
import gate_sandbox
import gates


class DeclaredPaths(unittest.TestCase):
    def test_no_declaration_changes_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual({}, gate_paths.options(root))
            pathlib.Path(root, "gate-paths.json").write_text("{}")
            self.assertEqual({}, gate_paths.options(root))

    def test_workspace_holds_paths_without_inspecting_their_contents(self):
        with tempfile.TemporaryDirectory() as root:
            declared = {"read_only": [root + "/absent"], "cache": root + "/cache"}
            pathlib.Path(root, "gate-paths.json").write_text(json.dumps(declared))
            self.assertEqual({"paths": declared}, gate_paths.options(root))

    def test_invalid_declarations_fail_instead_of_disappearing(self):
        with tempfile.TemporaryDirectory() as root:
            for declared in ([], {"other": []}, {"read_only": "relative"},
                             {"read_only": ["relative"]}, {"cache": []}):
                with self.subTest(declared=declared):
                    pathlib.Path(root, "gate-paths.json").write_text(json.dumps(declared))
                    with self.assertRaises((TypeError, ValueError)):
                        gate_paths.options(root)

    def test_declared_paths_reappear_after_masks_with_the_declared_access(self):
        with tempfile.TemporaryDirectory() as root:
            visible, cache, hidden = (root + "/" + name for name in
                                      ("visible", "cache", "hidden"))
            with patch.object(gate_sandbox, "BWRAP", "/box"), \
                 patch.object(gate_sandbox, "MASKED", (root,)):
                plain = gate_sandbox.argv("true", "/work", "/empty")
                line = gate_sandbox.argv("true", "/work", "/empty",
                                         {"read_only": [visible], "cache": cache})
            start = line.index("--chdir")
            self.assertEqual(["--ro-bind", visible, visible, "--bind", cache, cache],
                             line[start - 6:start])
            self.assertLess(line.index("--tmpfs"), start - 6)
            self.assertNotIn(hidden, line)
            self.assertEqual(plain, line[:start - 6] + line[start:])

    def test_gate_passes_declaration_to_the_box(self):
        declared = {"read_only": ["/assets"], "cache": "/cache"}
        with patch.object(gate_sandbox, "works", return_value=True), \
             patch.object(gate_sandbox, "argv", return_value=["true"]) as box, \
             patch("gates.runner.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = run.return_value.stderr = ""
            self.assertTrue(gates.run_gate("true", "/work", paths=declared).passed)
        self.assertEqual(declared, box.call_args.kwargs["paths"])

    def test_unconfined_gate_does_not_bind_paths(self):
        with patch.object(gate_sandbox, "argv") as box, patch("gates.runner.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = run.return_value.stderr = ""
            gates.run_gate("true", "/work", confine=False, paths={"cache": "/cache"})
        box.assert_not_called()

    def test_red_first_passes_the_declaration(self):
        declared = {"read_only": ["/assets"]}
        with patch.object(gates, "run_gate", return_value=gates.GateResult(0, "")) as run:
            gates.prove_red("true", "/work", paths=declared)
        self.assertEqual(declared, run.call_args.kwargs["paths"])

    def test_combined_tree_receives_the_campaign_workspace(self):
        from keep import Keeper
        keeper = object.__new__(Keeper)
        keeper.repo, keeper.workspace = "/repo", "/campaign"
        with patch("keep.combined_tree_red", return_value=None) as combined:
            keeper._combined_tree_red("card", "commit", ["true"])
        combined.assert_called_once_with("/repo", "card", "commit", ["true"],
                                         workspace="/campaign")
