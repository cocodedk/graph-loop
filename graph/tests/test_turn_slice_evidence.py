"""The turn-top slicer call's evidence trail and harness-rejection guard,
split from `test_turn_slice` at the 200-line cap. The rig is
`test_turn_slice`'s."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import slice_turn
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from test_turn_slice import routed, router, space

EXPECTED_TESTS = 4


class EvidenceTest(unittest.TestCase):
    def test_every_artifact_kind_travels_for_the_whole_lineage(self):
        root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
        for tid, body in (("P0", {"status": "sliced", "goal": "old", "files": ["app.py"]}),
                          ("T1", {"status": "needs_slice", "goal": "g", "files": ["app.py"],
                                  "triage": "work", "refused_why": "why", "sliced_from": "P0"})):
            (root / tid).mkdir(parents=True)
            (root / tid / "molecule.md").write_text(cardfile.dump(body))
        book = Backlog(root)
        s = space()
        for tid, names in (("T1", ("001-gate-output.txt", "009-zzz-diff.txt",
                                   "005-contract-answer.txt")),
                           ("P0", ("003-red-first.txt",))):
            calls = pathlib.Path(s.root) / "calls" / tid
            calls.mkdir(parents=True)
            for name in names:
                (calls / name).write_text("x")
        done = unittest.mock.Mock(returncode=0, stdout="published: T1.fix", stderr="")
        route = router(done)
        with routed(route):
            slice_turn.slice_pending(book, s)
        argv = " ".join(route.slicer_calls[0])
        # every kind, the oldest included — and the ancestor's findings too
        for name in ("T1-001-gate-output.txt", "T1-005-contract-answer.txt",
                     "T1-009-zzz-diff.txt", "P0-003-red-first.txt"):
            self.assertIn(".slicer-evidence/" + name, argv)


class HarnessRejectionTest(unittest.TestCase):
    def test_an_exhausted_harness_rejection_is_never_sliced(self):
        # B4 caps harness faults as `rejected` too; slicing one rewrites an
        # innocent card, so `rejected` stays out until triage can tell them apart
        from backlog_status import is_wall
        harness = {"id": "T1", "status": "rejected", "files": ["app.py"],
                   "rebuild_round": 3, "refused_why": "the diff review did not happen 3 rounds running"}
        self.assertFalse(is_wall(harness))
        contract = {"id": "T2", "status": "refused_contract", "files": ["app.py"], "replans": 2}
        self.assertFalse(is_wall(contract))            # no verdict, no slicing
        self.assertTrue(is_wall(dict(contract, triage="contract")))

    def test_the_verdict_and_the_rounds_are_boundaries_not_decoration(self):
        from backlog_status import is_wall
        # a verdict naming something other than the work or its contract routes
        # elsewhere, whatever the status
        self.assertFalse(is_wall({"id": "T2", "status": "refused_contract",
                                  "files": ["app.py"], "replans": 2, "triage": "environment"}))
        # a contract still wrong after its replans is the slicer's...
        self.assertTrue(is_wall({"id": "T2", "status": "refused_contract",
                                 "files": ["app.py"], "replans": 2, "triage": "contract"}))
        # ...but not before them, and not on a card the loop can still retry
        self.assertFalse(is_wall({"id": "T2", "status": "refused_contract",
                                  "files": ["app.py"], "replans": 1, "triage": "contract"}))
        self.assertFalse(is_wall({"id": "T3", "status": "needs_slice",
                                  "files": ["app.py"], "triage": "contract"}))
        # rejected + work slices only once the rebuild rounds are spent
        early = {"id": "T3", "status": "rejected", "files": ["app.py"],
                 "triage": "work", "rebuild_round": 1}
        self.assertFalse(is_wall(early))
        self.assertTrue(is_wall(dict(early, rebuild_round=3)))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
