"""The doctor's absolute-path rule and its one exemption: a live gate reaches
the helper by the main checkout's absolute path — the helper only, as a
complete word; every other absolute repository path is still a fault."""

from __future__ import annotations

import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
os.environ.setdefault("DRIVE_HELPER", "/repo/bin/sc")   # the repository's own command tool

from test_doctor import book

EXPECTED_TESTS = 2

class LiveGateAbsolutePathTest(unittest.TestCase):
    def test_a_live_gate_may_name_the_helper_by_absolute_path(self):
        # the live guard forbids worktree copies of the helper, so the
        # absolute path is the law there, not a fault
        from doctor import REPO, check_backlog
        from tools import helper
        live = book(gate=f"{helper()} story run-x",
                    gate_has_side_effects=True)
        self.assertEqual([], [c for c in check_backlog(live) if "absolute path" in c.what])
        code = book(gate=f"{REPO}/somewhere/gate.sh")
        self.assertTrue(any("absolute path" in c.what for c in check_backlog(code)))
        # only the helper is exempt: a live gate smuggling ANOTHER absolute
        # repo path beside the helper is still flagged
        HELPER = helper()
        mixed = book(gate=f"{HELPER} story run-x && bash {REPO}/other.sh",
                     gate_has_side_effects=True)
        self.assertTrue(any("absolute path" in c.what for c in check_backlog(mixed)))
        # and the helper only as a complete word: a lookalike is not exempt
        fake = book(gate=f"{HELPER}.bak story run-x", gate_has_side_effects=True)
        self.assertTrue(any("absolute path" in c.what for c in check_backlog(fake)))
        prefixed = book(gate=f"/tmp{HELPER} story run-x", gate_has_side_effects=True)
        self.assertTrue(any("absolute path" in c.what for c in check_backlog(prefixed)))
        assigned = book(gate=f"X={HELPER} story run-x", gate_has_side_effects=True)
        self.assertTrue(any("absolute path" in c.what for c in check_backlog(assigned)))



class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
