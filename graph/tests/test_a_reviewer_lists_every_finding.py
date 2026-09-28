"""A reviewer lists every finding at once, up to ten. With three, the grill spread its
questions over four stops and the diff reviewer its bugs over two paid repairs."""

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import providers  # before review: review imports it back
import review
from review_scope import VERDICT


def answer(findings: list[str]) -> str:
    return json.dumps({"review": "REJECT", "accept": False, "findings": findings})


class EveryFinding(unittest.TestCase):
    def test_five_findings_are_one_verdict_carrying_all_five(self):
        found = [f"finding {n}" for n in range(1, 6)]
        said = review._verdict_outcome(providers.Outcome("ok", text=answer(found)))
        self.assertEqual("REJECT", said.verdict)
        self.assertEqual("; ".join(found), said.text)

    def test_eleven_findings_are_still_no_verdict(self):
        said = review._verdict_outcome(providers.Outcome("ok", text=answer([f"f{n}" for n in range(11)])))
        self.assertEqual(("malformed", None), (said.kind, said.verdict))

    def test_the_answer_rule_asks_for_every_finding_up_to_ten(self):
        self.assertIn("every finding, at most ten", VERDICT)
        self.assertNotIn("at most three", VERDICT)


if __name__ == "__main__":
    unittest.main()
