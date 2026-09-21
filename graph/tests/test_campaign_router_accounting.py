"""Decision fees count as spend without consuming a build attempt."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from campaigns import CODE, campaign
from report import report

EXPECTED_TESTS = 4


class RouterAccountingTest(unittest.TestCase):
    def test_successful_routing_cost_is_included_once_in_total_spend(self):
        _, space = campaign([CODE])
        space.attempt("card", account="work", kind="ok", cost=1.25)
        space.event("routed", task="card", purpose="build", source="jev", cost=0.001)
        result = report(space)
        self.assertEqual(1.251, result["spend_known"])
        self.assertEqual(1, result["attempts"], "routing must not consume a build attempt")

    def test_a_paid_decision_still_counts_when_its_choice_is_rejected(self):
        _, space = campaign([CODE])
        space.event("routed", task="card", purpose="review", source="fallback", cost=0.001)
        self.assertEqual(0.001, report(space)["spend_known"])
        self.assertEqual(0, report(space)["attempts"])

    def test_an_offline_route_does_not_invent_spend(self):
        _, space = campaign([CODE])
        space.event("routed", task="card", purpose="build", source="fallback", cost=None)
        self.assertEqual(0, report(space)["spend_known"])
        self.assertEqual(0, report(space)["attempts"])

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
