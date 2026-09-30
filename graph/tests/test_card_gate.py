"""A card may carry its own fast gate. The builder runs that and never the full suite; the loop alone runs
the full suite after the build. Without a card gate the builder's gate is the profile's, as before, and
every builder is told never to start or wait on a background job (a paid turn per poll)."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tmp_root  # noqa: F401
from test_lean_run import PROFILE, Rig

EXPECTED_TESTS = 3
NO_BACKGROUND = "never start or wait on a background job"


class CardGate(Rig):
    def build_with(self, front):
        self.spec.write_text(f"---\n{front}---\nShow the overdue rest ring in amber.\n" if front else
                             "Show the overdue rest ring in amber.\n")
        tasks = []
        inner = self.builder(("ring.py", "amber\n"))

        def build(ws, task, prompt, tree, resume="", effort=""):
            tasks.append(task)
            return inner(ws, task, prompt, tree, resume, effort)
        self.run_it(build)
        return tasks[0], self.prompts[0]

    def test_a_card_gate_is_the_builders_and_the_full_suite_is_left_to_the_loop(self):
        task, prompt = self.build_with("gate: ./quick.sh ring\n")
        self.assertEqual("./quick.sh ring", task["gate"])
        self.assertIn("this card's own gate", prompt)
        self.assertIn("never the full suite", prompt)
        self.assertIn(NO_BACKGROUND, prompt)
        self.assertEqual([PROFILE["suite_command"]], self.suites)     # the loop's own check, untouched

    def test_without_one_the_builder_runs_the_profiles_suite_as_before(self):
        task, prompt = self.build_with("")
        self.assertEqual(PROFILE["suite_command"], task["gate"])
        self.assertIn("Run the suite with", prompt)
        self.assertNotIn("never the full suite", prompt)
        self.assertIn(NO_BACKGROUND, prompt)

    def test_a_gate_that_is_not_one_line_of_text_is_ignored(self):
        task, _prompt = self.build_with("gate: [a, b]\n")
        self.assertEqual(PROFILE["suite_command"], task["gate"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
