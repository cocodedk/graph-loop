"""A refusal names what is wrong: the answer rule (`review_scope.VERDICT`) says a REJECT
holds at least one finding. The legacy JSON reader did not hold it to that, so a refusal
with no finding, or only blank ones, read as a verdict with no reason in it."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import providers  # before review: review imports it back
import review


def read(answer: str) -> providers.Outcome:
    return review._verdict_outcome(providers.Outcome("ok", text=answer))


class RefusalNamesWhatIsWrong(unittest.TestCase):
    def test_a_refusal_with_no_finding_is_no_verdict(self):
        for findings in ("[]", '["", "  "]'):
            with self.subTest(findings=findings):
                said = read('{"review":"REJECT","accept":false,"findings":' + findings + "}")
                self.assertEqual(("malformed", None), (said.kind, said.verdict))

    def test_a_refusal_keeps_its_named_findings_and_drops_blank_ones(self):
        said = read('{"review":"REJECT","accept":false,"findings":["ring is grey", ""]}')
        self.assertEqual(("REJECT", "ring is grey"), (said.verdict, said.text))

    def test_an_accept_still_needs_no_finding(self):
        self.assertEqual("ACCEPT", read('{"review":"ACCEPT","accept":true,"findings":[]}').verdict)


if __name__ == "__main__":
    unittest.main()
