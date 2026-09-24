"""The live guard: a whitelist of exact command prefixes, no shell control
characters. Written before it was wired: each case is a way a builder could
reach the stack past a deny list."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from live_guard import decide, decide_file, decide_tool

EXPECTED_TESTS = 11
SC = "/repo/bin/sc"
PREFIXES = [f"{SC} free prd-app-04", f"{SC} journal *", "cat *", "ls *"]


class GuardTest(unittest.TestCase):
    def test_this_tasks_command_runs(self):
        self.assertEqual("", decide(f"{SC} free prd-app-04", PREFIXES))
        self.assertEqual("", decide(f"{SC} journal run-0123456789abcdef", PREFIXES))
        self.assertEqual("", decide("cat state/x.txt", PREFIXES))

    def test_a_bound_argument_cannot_be_changed(self):
        self.assertIn("not one of", decide(f"{SC} free prd-db-02", PREFIXES))

    def test_a_bound_command_is_the_whole_command(self):
        self.assertIn("not one of", decide(f"{SC} free prd-app-04 prd-db-02", PREFIXES))   # no extra target
        self.assertIn("not one of", decide(f"{SC} free", PREFIXES))                        # no fewer either

    def test_a_guard_that_cannot_read_the_call_denies(self):
        guard = pathlib.Path(__file__).resolve().parents[1] / "lib" / "live_guard.py"
        for stdin in ("not json", "", "[]", '{"tool_input": 5}'):
            done = subprocess.run([sys.executable, str(guard)], input=stdin, capture_output=True, text=True,
                                  env={"LIVE_ALLOWED_PREFIXES": "cat *"}, check=False)
            self.assertEqual(2, done.returncode, stdin)
        ok = subprocess.run([sys.executable, str(guard)], input='{"tool_name": "Bash", "tool_input": {"command": "cat x"}}',
                            capture_output=True, text=True, env={"LIVE_ALLOWED_PREFIXES": "cat *"}, check=False)
        self.assertEqual(0, ok.returncode)

    def test_a_verb_the_task_did_not_name_is_refused(self):
        self.assertIn("not one of", decide(f"{SC} reset-target dev-web-01", PREFIXES))

    def test_a_prefix_ends_at_a_word_boundary(self):
        self.assertIn("not one of", decide("catalog dump", PREFIXES))
        self.assertIn("not one of", decide("lsof -i", PREFIXES))

    def test_absolute_paths_and_wrappers_are_not_the_command(self):
        for cmd in ("docker ps", "/usr/bin/docker ps", "env docker ps", "bash -c 'docker ps'", "sh sc journal x"):
            self.assertIn("not one of", decide(cmd, PREFIXES), cmd)

    def test_no_shell_control_character_passes_even_after_a_good_prefix(self):
        for cmd in ("cat x; docker ps", "cat x && docker ps", "cat x | sh", "cat $(docker ps)", "cat `id`",
                    "cat x > /etc/passwd", "cat x < y", "ls\ndocker ps", "cat x \\\n docker"):
            self.assertIn("control", decide(cmd, PREFIXES), cmd)

    def test_only_the_reading_and_editing_tools_and_bash_exist_for_a_live_task(self):
        import os as _os
        _os.environ["LIVE_WORKTREE"] = "/w"
        self.addCleanup(_os.environ.pop, "LIVE_WORKTREE", None)
        for tool in ("Read", "Grep", "Glob"):
            self.assertEqual("", decide_tool(tool, "", PREFIXES), tool)
        for tool in ("Edit", "Write", "MultiEdit"):
            self.assertEqual("", decide_tool(tool, "", PREFIXES, path="/w/x", files=["/w/x"]), tool)
        for tool in ("Monitor", "Workflow", "Agent", "WebFetch", "mcp__docker__run", "NotebookEdit", ""):
            self.assertIn("not part of a live task", decide_tool(tool, "", PREFIXES), tool)
        self.assertEqual("", decide_tool("Bash", "cat x", PREFIXES))
        self.assertIn("not one of", decide_tool("Bash", "docker ps", PREFIXES))
        self.assertIn("foreground", decide_tool("Bash", "cat x", PREFIXES, background=True))   # never left running

    def test_a_writer_touches_only_the_tasks_own_files_resolved(self):
        import os as _os
        _os.environ["LIVE_WORKTREE"] = "/w"
        self.addCleanup(_os.environ.pop, "LIVE_WORKTREE", None)
        files = ["/w/state/card.txt", "/w/state/journal.txt"]
        self.assertEqual("", decide_file("/w/state/card.txt", files))
        self.assertEqual("", decide_file("/w/state/../state/journal.txt", files))          # resolved, still inside
        self.assertIn("not inside", decide_file("/w/state/../../repo/bin/sc", files))
        self.assertIn("not inside", decide_file("/repo/graph/lib/live_guard.py", files))
        self.assertIn("not inside", decide_file("/w/../repo/sc", files))                       # ../ out of the worktree
        self.assertIn("not one of", decide_file("/w/x", ["/repo/sc"]))    # a list entry outside the worktree grants nothing
        self.assertIn("not inside", decide_file("", files))              # an empty path is nowhere
        self.assertIn("not one of", decide_file("/w/state/card.txt", []))
        for tool in ("Edit", "Write", "MultiEdit"):
            self.assertIn("not inside", decide_tool(tool, "", PREFIXES, path="/etc/passwd", files=files), tool)
            self.assertEqual("", decide_tool(tool, "", PREFIXES, path="/w/state/card.txt", files=files), tool)

    def test_no_prefixes_means_nothing_runs(self):
        self.assertIn("not one of", decide("cat x", []))
        self.assertIn("not one of", decide("cat x", [""]))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
