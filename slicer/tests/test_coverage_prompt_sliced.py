"""A sliced parent's claim is checked against what actually replaced it.

Codex's review: the prompt told the reviewer to judge "the pieces listed under
it", and nothing listed them — the roster line carries id, status, files and the
goal's first line, and the parent's own contract had been left out.

Its next review: pointing the reviewer at `needs` was wrong too. A `needs` list
holds prerequisites, and it does not have to hold the replacements — on the live
tree `T12` is sliced, its `needs` names only `T1`, and seven other rows declare
`sliced_from: T12`. The pieces say whose replacement they are; the parent does
not, so the answer is read from them.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from asking import coverage_prompt

EXPECTED_TESTS = 3

ROWS = [
    {"id": "parent", "status": "sliced", "goal": "THE REPLACED CLAIM",
     "source": ["specs/greeting.md:1"], "needs": ["parent.piece"]},
    {"id": "parent.piece", "status": "done", "goal": "the piece",
     "done_when": "the piece passes"},
]

# T12's shape, and the reason `needs` cannot answer: the one name in it is a
# prerequisite that was finished long before, and the replacement names itself.
LIVE_SHAPE = [
    {"id": "T1", "status": "done", "goal": "the prerequisite"},
    {"id": "T12", "status": "sliced", "goal": "the replaced one", "needs": ["T1"],
     "source": ["specs/greeting.md:1"]},
    {"id": "T18", "status": "todo", "goal": "one replacement", "sliced_from": "T12",
     "files": ["a.py"], "gate": "set -e -o pipefail\nfalse", "done_when": "it passes"},
]

# T4's shape: its three pieces are their own top-level molecules named after it,
# written before anything recorded `sliced_from`. The name IS the link —
# `molecule.atom_id` builds `<parent>.<stem>`, and `backlog_tree` says an id is
# where the piece sits — so a parent with pieces like these is not an orphan.
BY_NAME = [
    {"id": "T2", "status": "done", "goal": "the prerequisite"},
    {"id": "T4", "status": "sliced", "goal": "the older replaced one", "needs": ["T2"],
     "source": ["specs/greeting.md:2"]},
    {"id": "T4.signin", "status": "done", "goal": "one piece", "done_when": "it passes"},
    {"id": "T4.close", "status": "done", "goal": "another piece", "done_when": "it passes"},
]


def prompt_for(rows: list[dict]) -> str:
    repo = pathlib.Path(tempfile.mkdtemp())
    source = repo / "greeting.md"
    source.write_text("## Goal\nReturn a greeting.\n", "utf-8")
    return coverage_prompt(repo, [source], rows)


class SlicedTest(unittest.TestCase):
    def test_a_sliced_parents_own_contract_is_in_the_prompt(self):
        text = prompt_for(ROWS)

        # In the contract and in nothing else: the roster line carries id,
        # status, files and the goal's first line, and `source` is not one.
        self.assertIn("specs/greeting.md:1", text)

    def test_the_replacement_is_read_from_the_piece_never_from_needs(self):
        text = prompt_for(LIVE_SHAPE)

        said = [line for line in text.splitlines() if line.startswith("T12 replaced by")]
        # Exactly the replacement, and nothing from `needs`: T1 is a
        # prerequisite, and naming it here would send the reviewer to a card
        # that covers none of T12's claim.
        self.assertEqual(["T12 replaced by: T18"], said)

    def test_pieces_named_after_their_parent_are_its_replacements_too(self):
        """A parent whose pieces predate `sliced_from` must not be reported as a
        claim with nowhere left to live: on the live tree T4 is exactly this,
        and the reviewer would have been sent looking for work that is done."""
        text = prompt_for(BY_NAME)

        said = [line for line in text.splitlines() if line.startswith("T4 replaced by")]
        self.assertEqual(["T4 replaced by: T4.signin, T4.close"], said)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
