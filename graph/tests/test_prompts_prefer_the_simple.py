"""Every stage's prompt pushes toward the simple, shared fix: the builder reuses, the repair fixes the cause
once, the grill lets standing rules and existing screens settle detail, and Jev refuses only new behaviour
without a test, so a change that existing tests cover is no refusal."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_body
import lean_judge
import tmp_root  # noqa: F401
from test_lean_run import Rig

EXPECTED_TESTS = 4


class Words(unittest.TestCase):
    def test_the_builder_is_told_to_choose_the_smallest_solution_and_reuse(self):
        prompt = lean_body.builder_prompt("spec", "gate.sh", "profile.md", "", False)
        self.assertIn("Choose the smallest coherent solution: reuse existing code and shared functions", prompt)

    def test_the_grill_lets_standing_rules_and_existing_screens_settle_detail(self):
        self.assertIn("Existing screens, components and the repository's standing rules may supply those "
                      "details: what they settle is no question", lean_body.grill_prompt("profile.md", "", "spec"))

    def test_jev_refuses_only_new_behaviour_without_a_test(self):
        self.assertIn("new behaviour", lean_judge.CHECK["no_tests"])
        self.assertIn("existing tests it leaves in place", lean_judge.CHECK["accept"])


class Repair(Rig):
    def test_a_repair_is_told_to_fix_the_cause_where_it_lives(self):
        self.run_it(self.builder(("ring.py", "grey\n"), ("ring.py", "amber\n")), suites=(False, True))
        self.assertIn("fix the cause in the function that owns it, once", self.prompts[1])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
