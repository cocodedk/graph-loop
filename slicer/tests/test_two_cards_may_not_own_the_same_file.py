"""Two cards that can run at the same time may not grant the same file.

A plan phase published four molecules that were the same composition under four
names, because the only thing enforced was "its name is new" and a rename
satisfies that for free. The prose instruction — "already covered, never plan
their work again" — was carrying the whole load. The waste was the smaller half:
one molecule claimed write access to five files five other cards already owned,
so two builders would have been authorised to write the same file in separate
worktrees, and whichever committed second would clobber the first or fail its
gate on a file that changed under it (2026-09-18, third campaign run).

It also defeated the exhaustion rule: publishing a duplicate IS a change to the
backlog, so a planner that can always invent a new name can keep the plan phase
alive for ever. The phase had no reason to stop and was killed by hand at 17
tasks.

What is checked here is ownership, not meaning: a file belongs to one unsettled
card unless the two cards are ordered, which needs no reading of the repository.
Ordered is enough — a card that waits on another gets its worktree after that
one landed, which is how a molecule's own stages already share a file.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from contracts import validate

EXPECTED_TESTS = 6


def answer(needs: list[str] | None = None) -> dict:
    return {"result": "MOLECULE", "reason": "one gap", "molecule": {
        "name": "assemble", "source": ["specs/greeting.md:2"],
        "goal": "assemble the greeting from its parts", "why": "nothing composes them",
        "needs": needs or [], "atoms": [], "files": ["app.py"],
        "gate": "set -e -o pipefail\nfalse", "done_when": "the assembly test passes"}}


def owner(status: str = "todo", **more: object) -> dict:
    row = {"id": "parse", "status": status, "needs": [], "files": ["app.py"],
           "goal": "parse the greeting"}
    row.update(more)
    return row


class OneOwnerPerFile(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        (self.repo / "specs").mkdir()
        (self.repo / "specs" / "greeting.md").write_text("# Greeting\nIt is returned.\n", "utf-8")
        (self.repo / "app.py").write_text("present = True\n", "utf-8")

    def check(self, answered: dict, rows: list[dict]) -> dict:
        return validate(answered, repo=self.repo, sources=[self.repo / "specs"], rows=rows)

    def test_an_unordered_card_may_not_take_a_file_another_card_owns(self):
        with self.assertRaisesRegex(ValueError, r"app\.py.*parse"):
            self.check(answer(), [owner()])

    def test_waiting_on_that_card_makes_it_legal(self):
        # The molecule's own stages already share files this way: stage 2 waits
        # for stage 1, so its worktree is cut after stage 1 landed.
        self.check(answer(needs=["parse"]), [owner()])

    def test_a_settled_card_owns_nothing(self):
        # Its work is committed, so a later card granting the same file is
        # building on landed code rather than racing a builder.
        self.check(answer(), [owner("done")])
        self.check(answer(), [owner("dropped")])

    def test_the_refusal_says_what_to_do_instead(self):
        try:
            self.check(answer(), [owner()])
        except ValueError as refused:
            said = str(refused)
        self.assertIn("NO_GAP", said)          # the work may already be planned
        self.assertIn("needs", said)           # or this molecule waits on it


    def test_a_sliced_card_owns_nothing_either(self):
        # Its work belongs to its children now and no builder is ever offered
        # it, so holding its files would refuse every card cut from it.
        rows = [owner("sliced"), {"id": "parse.first", "status": "todo", "needs": [],
                                  "files": ["other.py"], "sliced_from": "parse",
                                  "goal": "the first piece"}]
        self.check(answer(), rows)

    def test_an_atom_is_caught_the_same_way(self):
        # The molecule that did this in the campaign had atoms; the grant that
        # collides is the atom's, and the refusal names the atom's whole id.
        made = answer()["molecule"]
        made.pop("files"), made.pop("gate"), made.pop("done_when")
        made["atoms"] = [{"name": "second", "stage": 1, "goal": "assemble it",
                          "files": ["app.py"], "gate": "set -e -o pipefail\nfalse",
                          "done_when": "the assembly test passes"}]
        with self.assertRaisesRegex(ValueError, r"assemble\.second would hold it"):
            self.check({"result": "MOLECULE", "reason": "one gap", "molecule": made}, [owner()])


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
