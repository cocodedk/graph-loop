"""A refused contract is not written over a decision made while the review ran.

The contract review is a model call of minutes, and the card it started from can
be dropped, held or rewritten in them by another writer — the decider, a drop, a
person. The refusal that comes back was decided from the older card, so writing
`refused_contract` buries whatever settled it. The rig lives in `test_loop`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import tmp_root  # noqa: F401 — keep temporary files under the test root
from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 2


def dropping(fakes: Fakes, book):
    """The reviewer answers, and another writer drops the card while it ran."""
    real = fakes.reviewer

    def reviewer(prompt, **kwargs):
        out = real(prompt, **kwargs)
        book.set_status("T1", "dropped", refused_why="decided against")
        return out

    return reviewer


class ContractRefusalCardMovedTest(unittest.TestCase):
    def test_blocked_review_footer_parks_before_contract_refusal(self):
        import tempfile
        from types import SimpleNamespace
        from unittest import mock

        from distress import INSTRUCTION, TEMPLATE
        from loop_contract import contract
        from review import _one_review
        from test_distress import BLOCKED, DONE
        from test_replan import book_with
        from workspace import Workspace
        for footer in (BLOCKED, DONE.replace('false, "why": ""',
                       'true, "why": "missing inputs"')):
            book = book_with(status="todo")
            space = Workspace(tempfile.mkdtemp())
            tree = mock.Mock(path="unused")
            text = '{"review":"ACCEPT","accept":true,"findings":[]}\n' + footer
            with mock.patch("review.codex_text", return_value=Outcome("ok", text=text)) as call:
                loop = SimpleNamespace(backlog=book, space=space,
                    review=lambda prompt, **_: _one_review("codex", prompt, "model", "", "high", 1))
                out = contract(loop, book.task("T1"), tree)
            self.assertIsNotNone(out)
            self.assertEqual("blocked", out.state)
            self.assertEqual("blocked_by_agent", book.task("T1")["status"])
            self.assertFalse(book.startable())
            self.assertEqual(out.why, next(e["why"] for e in space.events()
                                          if e["kind"] == "needs_a_person"))
            self.assertIn(INSTRUCTION + TEMPLATE, call.call_args.args[1])
            tree.remove.assert_not_called()


    def test_a_card_dropped_while_the_contract_review_ran_stays_dropped(self):
        fakes = Fakes(review=[Outcome("ok", verdict="REJECT", text="1. too broad")])
        loop, book, space = loop_for(task(), fakes)
        loop.review = dropping(fakes, book)
        loop.run_task(book.task("T1"))
        self.assertEqual("dropped", book.task("T1")["status"])
        self.assertIn("card_moved", [row.get("kind") for row in space.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
