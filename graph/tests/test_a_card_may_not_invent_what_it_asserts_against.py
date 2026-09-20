"""A card built an extractor for a page format nobody had seen, and it went green.

The gate IS the verdict, so a file the gate never names is a file whose content
the verdict does not pin. The extraction card granted itself four files under
`test/resources`, passed the DIRECTORY to its test rather than the files, and
said in its own note that the fixtures were "minimal pages in the shape of the
post JSON embedded in x.com's own public page". Nothing in the repository
declared that shape. The builder wrote the fixture and the code to match it, the
gate proved they matched, and the card was kept (2026-09-18).

Measured on the twelve cards that campaign planned: ten carried a file grant, and
exactly the two extraction cards granted a file their own gate never named. The
other eight named every file they granted, so this is narrow rather than general.

It is a question to the reviewer, not a refusal, and the reason is in the same
measurement: the extraction gate's own `java -cp "$OUT" …Test app/src/test/resources`
is the honest shape too. A gate that runs a whole directory of tests names no file
under it and invents nothing. What tells the two apart is whether the shape that
file imitates is declared anywhere the loop can read, which no rule here can see
and a reviewer can.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from contract import contract_prompt, contract_text
from contract_fixtures import question, unpinned

EXPECTED_TESTS = 7

GATE = ('set -e -o pipefail\nOUT="$(mktemp -d)"\n'
        'javac -d "$OUT" app/src/main/java/PostTextExtractor.java '
        'app/src/test/java/PostTextExtractorTest.java\n'
        'java -cp "$OUT" PostTextExtractorTest app/src/test/resources\n')


def card(**more: object) -> dict:
    task = {"id": "T1", "goal": "return the whole post text", "done_when": "the gate exits 0",
            "gate": GATE,
            "files": ["app/src/main/java/PostTextExtractor.java",
                      "app/src/test/java/PostTextExtractorTest.java",
                      "app/src/test/resources/long-post-page.html",
                      "app/src/test/resources/long-post-expected.txt"]}
    task.update(more)
    return task


class TheGatePinsWhatTheCardMayWrite(unittest.TestCase):
    def test_the_fixtures_the_gate_never_names_are_the_ones_listed(self):
        self.assertEqual(["app/src/test/resources/long-post-page.html",
                          "app/src/test/resources/long-post-expected.txt"], unpinned(card()))

    def test_a_card_whose_gate_names_every_file_is_asked_nothing(self):
        named = card(files=["app/src/main/java/PostTextExtractor.java",
                            "app/src/test/java/PostTextExtractorTest.java"])
        self.assertEqual([], unpinned(named))
        self.assertEqual("", question(named))

    def test_a_card_with_no_gate_is_asked_nothing(self):
        # nothing to pin against, and the slicer refuses such a card anyway
        self.assertEqual("", question(card(gate="")))

    def test_a_gate_that_names_no_file_of_its_own_is_asked_nothing(self):
        """`pytest tests/` names no fixture under it and invents nothing. A gate
        that skipped NONE of its card's files has drawn no line, so there is no
        signal here — listing every granted file would be the noise that teaches
        a reviewer to wave the paragraph through."""
        self.assertEqual([], unpinned(card(gate="set -e -o pipefail\npytest tests/\n")))
        self.assertEqual("", question(card(gate="set -e -o pipefail\npytest tests/\n")))

    def test_the_question_names_each_file_and_says_what_refusing_means(self):
        said = question(card())
        for path in unpinned(card()):
            self.assertIn(f"  - {path}\n", said)
        self.assertIn("OUTSIDE this repository", said)
        self.assertIn("refuse the card", said)

    def test_the_reviewer_is_asked_it(self):
        # NOT the path: `contract_text` prints the card's whole file list, so a
        # prompt holding the path proves nothing about the question being there.
        # The first version of this test asserted the path and passed with the
        # question unwired.
        said = contract_prompt(card())
        self.assertIn("names some of the files it grants and not these", said)
        self.assertIn("  - app/src/test/resources/long-post-page.html\n", said)
        self.assertNotIn("names some of the files it grants and not these",
                         contract_prompt(card(files=["app/src/main/java/PostTextExtractor.java",
                                                     "app/src/test/java/PostTextExtractorTest.java"])))

    def test_it_does_not_move_an_accepted_cards_contract(self):
        """The digest is `contract_text`, and the question is added outside it —
        the same care the used-but-not-granted question was written with, or
        every card already accepted would need reviewing again."""
        self.assertNotIn("OUTSIDE this repository", contract_text(card()))


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
