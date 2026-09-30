"""A card that passes $3.99 rings a bell: one mail with the spend and the budget, and the build carries on.
The plug at the card's budget is what stops it (`test_card_budget`); the bell only says look now."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401
from providers import Outcome
from test_lean_run import Rig

EXPECTED_TESTS = 3


class Bell(Rig):
    def calls(self, costs, suites):
        costs = list(costs)

        def build(ws, task, prompt, tree, resume="", effort=""):
            (pathlib.Path(tree.path) / "ring.py").write_text(f"v{len(costs)}\n")
            return Outcome("ok", cost=costs.pop(0), session="s1")
        landed = self.run_it(build, suites=suites)
        bells = [mail for mail in self.mails if "passed" in mail[0]["subject"]]
        return landed, bells, [row for row in self.ws.events() if row["kind"] == "lean_bell"]

    def test_the_bell_rings_once_at_the_threshold_and_the_build_carries_on_and_lands(self):
        landed, bells, events = self.calls([4.5, 5.0], suites=(False, True))
        self.assertTrue(landed)
        (kw, body), = bells
        self.assertIn("rest-ring passed $3.99", kw["subject"])
        for text in ("$4.50", "$8", "rest-ring", "carries on"):
            self.assertIn(text, body)
        self.assertEqual([4.5], [row["spent"] for row in events])          # not again at $5.00

    def test_a_card_under_the_threshold_never_rings(self):
        landed, bells, events = self.calls([1.0, 3.9], suites=(False, True))
        self.assertTrue(landed)
        self.assertEqual(([], []), (bells, events))

    def test_a_card_that_reaches_its_budget_in_one_call_rings_and_is_stopped(self):
        landed, bells, _ = self.calls([8.5], suites=(False,))
        self.assertFalse(landed)
        self.assertEqual(1, len(bells))
        self.assertIn("stopped", self.mails[-1][1])                          # the plug's mail comes after


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
