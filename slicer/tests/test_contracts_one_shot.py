"""A temporary proof and its lasting check survive planning and publication."""

import unittest

import test_contracts
import asking
from backlog import Backlog
from contract import contract_text
from tree import publish

EXPECTED_TESTS = 2


class OneShotContracts(unittest.TestCase):
    def test_the_planner_names_both_fields_and_the_card_keeps_them(self):
        rig = test_contracts.Contracts()
        rig.setUp()
        lasting = "set -e -o pipefail\npython3 -m unittest test_app.py"
        answer = rig.check(rig.atom(gate_until_kept=True, gate_when_kept=lasting))
        tree = rig.repo / "tree"
        tree.mkdir()
        publish(tree, answer["molecule"])
        card = Backlog(tree).tasks()[0]
        self.assertIs(True, card["gate_until_kept"])
        self.assertEqual(lasting, card["gate_when_kept"])
        question = asking.prompt(rig.repo, [rig.source], [])
        for key in ("gate_until_kept", "gate_when_kept"):
            self.assertIn(key, question)
            self.assertIn(key, contract_text(card))

    def test_the_marker_is_boolean_and_the_lasting_gate_is_text(self):
        rig = test_contracts.Contracts()
        rig.setUp()
        for fields in ({"gate_until_kept": "true"}, {"gate_when_kept": False}):
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, next(iter(fields))):
                rig.check(rig.atom(**fields))


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        self.assertEqual(EXPECTED_TESTS + 1,
                         unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases())


if __name__ == "__main__":
    unittest.main()
