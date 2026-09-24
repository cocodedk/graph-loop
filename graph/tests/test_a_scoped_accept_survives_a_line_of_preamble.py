"""A perfect ACCEPT was thrown away twice: for a fence, and for a fourth observation.

The diff reviewer answers a four-key shape — review, accept, findings and
observations — and `review_scope.read` is what knows it. It read the WHOLE reply,
so a ```json fence, a line of preamble or a closing sentence was a
`JSONDecodeError`. And it refused a fourth observation outright, though an
observation is non-blocking by construction: it rejects nothing and never
reaches a builder.

The cost is not one review. A verdict that cannot be read is `malformed`, which
is a harness fault, which is filed outside the tasks — the driver stood down
with three cards still to build, on a review that said ACCEPT. Two of five diff
reviews in the fifth campaign went that way. The fence half retried out of it,
because a fence is the model's own coin flip; the fourth observation could not,
because the same diff draws the same four observations every time, and one card
was refused twice in a row on it (2026-09-18).

These go through `review_scope.read` and not through `review._read_review`,
because the loop calls both: the reader picks the verdict, and then
`loop_diff_review` hands the SAME text back to `review_scope.validate` for the
diff-line anchors. A fix in the reader alone leaves the second call refusing what
the first just accepted — which is what the first attempt at this did, with a
green test beside it.
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import providers  # noqa: F401 — the transport door, imported first so its pair initialises
import review_scope
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from review import _read_review

EXPECTED_TESTS = 8

DIFF = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-one\n+two\n"
SEEN = ["the id-only URL relies on a redirect nobody has observed",
        "done_when names an I/O property the test never asserts",
        "the gate script sits at the repo root outside the contract's file list"]
ACCEPT = json.dumps({"review": "ACCEPT", "accept": True, "findings": [],
                     "observations": SEEN})


def both(text: str) -> tuple[str | None, list]:
    """What the loop does to one reply: read the verdict, then re-read the same
    text for its diff-line anchors (`loop_diff_review`). Either refusing is a
    harness fault and a thrown-away build."""
    verdict, carried = _read_review(text)
    return verdict, review_scope.validate(carried, DIFF)["observations"]


class AScopedVerdictSurvivesProse(unittest.TestCase):
    def test_the_bare_answer_still_reads(self):
        self.assertEqual(("ACCEPT", SEEN), both(ACCEPT))

    def test_a_line_of_preamble_does_not_lose_it(self):
        self.assertEqual(("ACCEPT", SEEN), both("Here is my review.\n" + ACCEPT))

    def test_a_trailing_line_does_not_lose_it(self):
        self.assertEqual(("ACCEPT", SEEN), both(ACCEPT + "\nThat is all."))

    def test_a_fence_does_not_lose_it(self):
        self.assertEqual(("ACCEPT", SEEN), both("```json\n" + ACCEPT + "\n```"))


class AFourthObservationCostsNothing(unittest.TestCase):
    def test_the_verdict_stands_and_the_extra_is_dropped(self):
        wordy = json.dumps({"review": "ACCEPT", "accept": True, "findings": [],
                            "observations": SEEN + ["unrequested www. stripping"]})
        self.assertEqual(("ACCEPT", SEEN), both(wordy))

    def test_a_fourth_finding_still_refuses_it(self):
        # findings block and cost a rebuild each: three is the declared budget
        blocker = {"diff_line": 6, "requirement": "done_when", "problem": "wrong",
                   "evidence": "the changed value fails the declared result"}
        with self.assertRaises(ValueError):
            review_scope.read(json.dumps({"review": "REJECT", "accept": False,
                                          "findings": [blocker] * 4, "observations": []}))


class TheShapeStaysClosed(unittest.TestCase):
    def test_a_second_answer_beside_it_refuses_the_lot(self):
        for beside in ("REVIEW: ACCEPT", "REVIEW: REJECT", ACCEPT):
            with self.subTest(beside=beside):
                self.assertIsNone(_read_review(ACCEPT + "\n" + beside)[0])
                with self.assertRaises(ValueError):
                    review_scope.read(ACCEPT + "\n" + beside)

    def test_an_unknown_key_is_still_no_verdict(self):
        odd = json.loads(ACCEPT)
        odd["confidence"] = 0.9
        self.assertIsNone(_read_review(json.dumps(odd))[0])


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
