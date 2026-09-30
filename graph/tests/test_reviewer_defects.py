"""The reviewer refuses a defect it can name, so the repair loop fixes it, instead of accepting it with a note that
nothing requires anyone to act on. It accepts with findings only for style, a missing test or a stated limit."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tmp_root  # noqa: F401
from providers import Outcome
from test_lean_run import ACCEPT, Rig, show

EXPECTED_TESTS = 2


class Refuses(Rig):
    def prompt(self):
        self.run_it(self.builder(("ring.py", "amber\n")), reviews=(ACCEPT,))
        return self.reviews[0]

    def test_the_prompt_refuses_any_defect_it_can_name_and_accepts_notes_only_for_the_small_things(self):
        prompt = self.prompt()
        for words in ("any defect you can name", "wrong for some real input or use", "style, a stated limit"):
            self.assertIn(words, prompt)
        self.assertNotIn("List anything rarer as a finding, and accept", prompt)

    def test_a_defect_refusal_is_repaired_and_the_change_lands(self):
        refused = Outcome("ok", verdict="REJECT", text="a corrupt log line crashes the list")
        landed = self.run_it(self.builder(("ring.py", "grey\n"), ("ring.py", "amber\n")),
                             suites=(True, True), reviews=(refused, ACCEPT))
        self.assertTrue(landed)
        self.assertIn("a corrupt log line crashes the list", self.prompts[1])
        self.assertEqual("amber\n", show(self.repo, "lean/rest-ring", "ring.py"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
