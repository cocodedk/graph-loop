"""The file fence says where bytes landed, never whose fault that was.

Run 6 of the x-post-text-extractor campaign paid for this. Two builders
answered DONE with every test green, left compiler output in a scratch
directory the sandbox would not let them remove, and the fence refused both
cards. TRIAGE named the refusal `work`, `is_wall` read that as a card cut too
wide, and the next plan phase re-sliced two cards that were right — one of them
close to a card that had built cleanly the run before.

So the signature row names no cause. The paths, the card's files and the
builder's own answer are all in the evidence; the model reads them. Until it
does, the card is a harness fault and the plan phase puts it back once.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import resources
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from backlog_status import is_wall
from plan_phase import requeue_faults
from providers import Outcome
from triage import triage_pending
from triage_evidence import Ending
from triage_signatures import classify
from workspace import Workspace

EXPECTED_TESTS = 6
# The two refusals of run 6, spelled as the loop spelled them.
RUN_6 = ("the builder wrote outside its files: buildtmp.oXsBJW/PostLink.class",
         "the builder wrote outside its files: .buildout/FetchFailureMessage.class")
CARD = {"id": "T1", "status": "todo", "files": ["src/PostLink.java"],
        "gate": "false"}


def ending(why: str = RUN_6[0]) -> Ending:
    return Ending("T1", dict(CARD),
                  ({"kind": "claimed"},
                   {"kind": "failed", "step": "scope", "why": why}),
                  {}, ())


class TheSignatureTest(unittest.TestCase):
    def test_a_scope_refusal_names_no_cause(self):
        said = classify(ending())
        self.assertEqual(("unknown", "scope"), (said.verdict, said.signature))

    def test_neither_run_6_refusal_blames_the_work(self):
        for why in RUN_6:
            with self.subTest(why=why):
                self.assertNotEqual("work", classify(ending(why)).verdict)

    def test_the_refusal_itself_still_reaches_the_evidence(self):
        """`why` is what the model reads the paths from, so it survives."""
        self.assertIn("outside its files", classify(ending()).why)


class TheCardTest(unittest.TestCase):
    """Through the loop's own door, not the signature alone: `classify` is one
    reader of this refusal and `is_wall` is the one that acts on it."""

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        path = self.root / "backlog.yaml"
        path.write_text(yaml.safe_dump({"tasks": [dict(CARD)]}), "utf-8")
        self.book = Backlog(path)
        self.space = Workspace(self.root / "campaign")
        # The catch-up first, on an empty log: it spends nothing, and without
        # it the refusal below would be caught up too and never reach a model.
        triage_pending(self.book, self.space,
                       call=mock.Mock(side_effect=AssertionError("catch-up paid")))

    def refusal(self, why: str = RUN_6[0]) -> None:
        self.space.event("claimed", task="T1")
        self.space.event("failed", task="T1", step="scope", why=why)
        self.space.event("released", task="T1")
        self.book.set_status("T1", "out_of_scope", refused_why=why)

    def answer(self, verdict: str, why: str) -> dict:
        with mock.patch.object(resources, "belt", return_value=[
                resources.Resource("claude", "work", "opus")]):
            triage_pending(self.book, self.space,
                           call=lambda _prompt, _resource: Outcome(
                               "ok", text=json.dumps({"verdict": verdict, "why": why})))
        return self.book.task("T1")

    def test_the_slicer_does_not_take_a_card_the_fence_refused(self):
        """Run 6's own cause, in the builder's own words: it was denied the
        gate it was told to run, and improvised a scratch directory it was
        then denied the right to remove."""
        self.refusal()
        card = self.answer("harness", "the builder was denied its own gate")
        self.assertEqual("harness", card["triage"])
        self.assertFalse(is_wall(card))

    def test_the_plan_phase_puts_that_card_back_once(self):
        self.refusal()
        self.answer("harness", "the builder was denied its own gate")
        self.assertEqual(1, requeue_faults(self.book, self.space))
        self.assertEqual("todo", self.book.task("T1")["status"])
        self.assertEqual(0, requeue_faults(self.book, self.space))

    def test_the_model_may_still_blame_the_work_and_then_it_is_a_wall(self):
        """The narrow grant is the case slicing exists for, and it survives:
        the refusal reaches the slicer when the model reads the paths that
        way, and only then."""
        self.refusal()
        card = self.answer("work", "it had to edit a file it was never granted")
        self.assertEqual("work", card["triage"])
        self.assertTrue(is_wall(card))


if __name__ == "__main__":
    unittest.main()
