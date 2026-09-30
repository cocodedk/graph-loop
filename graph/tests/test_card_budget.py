"""A card has a budget of $8; a card that spends it is stopped and the mail names the cards after it for review.
A session's reported cost is its running total, so a resumed call replaces the card's spend and a fresh session
adds to it; each builder call is capped at what is left, and a card at its budget starts no repair."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lean_budget
import lean_run
import tmp_root  # noqa: F401
from providers import Outcome
from test_lean_run import Rig

EXPECTED_TESTS = 4
RED = "FAILED: AmberTest > overdue"


class Budget(Rig):
    def calls(self, costs, sessions=None, suites=(False,) * 3):
        """Run a feature whose builder answers with `costs`; the cap each call was given, and the mail."""
        caps, sessions = [], list(sessions or ["s1"] * len(costs))
        costs = list(costs)

        def build(ws, task, prompt, tree, resume="", effort=""):
            caps.append(task["budget"])
            self.prompts.append(prompt)
            (pathlib.Path(tree.path) / "ring.py").write_text(f"v{len(caps)}\n")
            return Outcome("ok", cost=costs.pop(0), session=sessions.pop(0))
        for name in ("zz-next.md", "zz-after.md", "lessons.md"):
            (self.spec.parent / name).write_text("Later.\n")
        self.run_it(build, suites=suites)
        return caps

    def test_each_call_is_capped_at_what_is_left_and_a_fresh_session_adds(self):
        self.assertEqual([8, 5, 2.5], self.calls([3.0, 5.5, 6.0]))                      # resumed: the running total
        self.assertEqual([8, 5, 4], self.calls([3.0, 1.0, 1.0], ["", "", ""]))          # fresh sessions add up

    def test_a_card_at_its_budget_starts_no_repair_and_the_stop_names_the_cards_after_it(self):
        caps = self.calls([8.5])
        self.assertEqual([8], caps)
        self.assertEqual(1, len(self.prompts))
        (_kw, body), = self.mails
        for text in ("budget of $8", "Reslice or simplify", "zz-next", "zz-after"):
            self.assertIn(text, body)
        self.assertNotIn("lessons", body)
        self.assertIn("lean_status: stopped", self.spec.read_text())

    def test_a_card_under_its_budget_is_unchanged(self):
        self.assertEqual([8, 6.5], self.calls([1.5, 1.6], suites=(False, True))[:2])
        self.assertEqual([], self.mails)


class Helpers(unittest.TestCase):
    def test_spent_and_left(self):
        self.assertEqual(3.0, lean_budget.spent(0.0, Outcome("ok", cost=3.0), True))
        self.assertEqual(5.5, lean_budget.spent(3.0, Outcome("ok", cost=5.5), True))
        self.assertEqual(4.0, lean_budget.spent(3.0, Outcome("ok", cost=1.0), False))
        self.assertEqual(3.0, lean_budget.spent(3.0, Outcome("ok", cost=None), True))
        self.assertEqual(5.0, lean_budget.left(3.0))
        self.assertEqual(8, lean_run.CARD_BUDGET)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
