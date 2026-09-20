"""The contract reviewer is asked about each used file by name.

The rule was already there — "refuse it if its files do not cover what its gate
can fail on" — and it worked: one card was refused before any builder started,
because the reviewer happened to reason that `PostPageFetcher.fetchPostPage`
throws on 429 and the card did not grant that file. Its sibling in the same
molecule was the same shape, was accepted, and its builder spent a full build
before the file fence stopped it: "the builder wrote outside its files"
(2026-09-18, the first real campaign run).

So the check exists and is unreliable, not missing. What made the branch
reviewer reliable in the same campaign was being asked to take the items ONE AT
A TIME by name instead of reading a general clause, and that is what this does:
the card's own `uses` files are listed, and the reviewer answers for each.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from prompts import contract_prompt

EXPECTED_TESTS = 4

IMPOSSIBLE = {
    "id": "T2", "goal": "the request names the app",
    "files": ["src/test/FetchHeadersTest.java"], "may_add_files": True,
    "gate_files_are_the_work": True,
    "gate": "set -e -o pipefail\nfalse", "done_when": "the header test passes",
    "uses": ["src/main/PostPageFetcher.java:fetchPostPage"]}


class UsedFilesAreNamedTest(unittest.TestCase):
    def test_every_used_file_is_put_to_the_reviewer_by_name(self):
        said = contract_prompt(IMPOSSIBLE)
        self.assertIn("src/main/PostPageFetcher.java", said)
        self.assertIn("one at a time", said.lower())

    def test_the_question_asked_is_whether_the_gate_fails_on_that_file(self):
        said = contract_prompt(IMPOSSIBLE)
        self.assertIn("fail", said)
        self.assertIn("grant", said)

    def test_a_file_the_card_already_grants_is_not_asked_about(self):
        """It is already covered, so asking would teach the reviewer to say no
        to cards that are right."""
        card = dict(IMPOSSIBLE, files=["src/test/FetchHeadersTest.java",
                                       "src/main/PostPageFetcher.java"])
        said = contract_prompt(card)
        self.assertNotIn("one at a time", said.lower())

    def test_a_card_that_uses_nothing_is_asked_nothing(self):
        said = contract_prompt({key: value for key, value in IMPOSSIBLE.items()
                                if key != "uses"})
        self.assertNotIn("one at a time", said.lower())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
