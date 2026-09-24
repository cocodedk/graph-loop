"""An activation writes the gate that was approved, never one worked out again.

Activation called `sweep`, which asks the repair what it would do NOW: the
approval said what each card's gate would become, and a repair edited between
the approval and the recovery that applies it landed different text under that
approval (astra's round-4 finding 11). What was approved and what happens are
one record, so the effects are applied, not recomputed. The rig is
`test_two_repairs_on_one_card.previewing`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import triage_repairs
from test_two_repairs_on_one_card import GATE, previewing
from triage_routes import activate_preview

EXPECTED_TESTS = 1


class ApprovedRepairTest(unittest.TestCase):
    def test_a_repair_changed_after_the_approval_does_not_write_its_new_text(self):
        book, space = previewing("mute-gate")
        approved = triage_repairs.print_then_grade(GATE)   # what the decider was shown

        with mock.patch.dict(triage_repairs.REPAIRS,
                             {"mute-gate": lambda gate: gate + " # changed since"}):
            activate_preview(book, space, space.events())

        self.assertEqual(approved, book.task("T1")["gate"])
        self.assertTrue([one for one in space.events()
                         if one.get("kind") == "triage_activation"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
