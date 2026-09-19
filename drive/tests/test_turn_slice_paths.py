"""The turn-top slicer call's gap and person paths, split from
`test_turn_slice` at the 200-line cap. The rig is `test_turn_slice`'s."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import slice_turn
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_turn_slice import routed, router, space, tree_with

EXPECTED_TESTS = 13

class GapPersonOnceTest(unittest.TestCase):
    def test_a_gap_needs_person_is_not_retried_until_sources_move(self):
        book = tree_with({"id": "T1", "status": "done", "goal": "g", "files": ["app.py"]})
        s = space()
        done = unittest.mock.Mock(returncode=2, stdout="needs_person: the spec contradicts itself", stderr="")
        route = router(done)
        with routed(route):
            slice_turn.slice_pending(book, s)                         # turn one: asks, alerts
            slice_turn.slice_pending(book, s)                         # turn two: silent
        self.assertEqual(1, len(route.slicer_calls))
        s.event("sources_declared", sources=["simulation/spec"])
        route = router(done)
        with routed(route):
            slice_turn.slice_pending(book, s)                         # sources moved: asks again
        self.assertEqual(1, len(route.slicer_calls))



class NeedsPersonTest(unittest.TestCase):
    def test_a_needs_person_answer_holds_the_card_and_alerts_once(self):
        book = tree_with({"id": "T1", "status": "needs_slice", "goal": "g",
                          "files": ["app.py"], "triage": "work", "refused_why": "the gate said why"})
        s = space()
        done = unittest.mock.Mock(returncode=2, stdout="needs_person: the spec is silent here", stderr="")
        with routed(router(done)):
            slice_turn.slice_pending(book, s)
        row = book.task("T1")
        self.assertTrue(row.get("blocked_by_human"))
        self.assertIn("spec is silent", row.get("refused_why"))
        self.assertEqual(1, len(s.alerts()))



class NoSourcesTest(unittest.TestCase):
    def test_a_campaign_with_no_declared_sources_is_not_sliced(self):
        book = tree_with({"id": "T1", "status": "needs_slice", "goal": "g", "files": ["app.py"], "triage": "work", "refused_why": "the gate said why"})
        s = space(sources=())
        with unittest.mock.patch("subprocess.run") as run:
            slice_turn.slice_pending(book, s)
        run.assert_not_called()
        self.assertIn("slice_skipped", [e.get("kind") for e in s.events()])



class SourceGapTest(unittest.TestCase):
    def test_an_idle_queue_with_no_wall_slices_the_source_gap(self):
        book = tree_with({"id": "T1", "status": "done", "goal": "g", "files": ["app.py"]})
        s = space()
        done = unittest.mock.Mock(returncode=0, stdout="covered: unchanged", stderr="")
        route = router(done)
        with routed(route):
            slice_turn.slice_pending(book, s)
        self.assertNotIn("--target", route.slicer_calls[0])     # the gap path, not a wall




class GapCapTest(unittest.TestCase):
    def test_answered_gap_failures_hit_the_cap_and_alert_once(self):
        from replan import MAX_REPLANS
        book = tree_with({"id": "T1", "status": "done", "goal": "g", "files": ["a.py"]})
        s = space()
        for _ in range(MAX_REPLANS):
            s.event("slice_finished", task="the sources", rc=1, state="refused")
        route = router(unittest.mock.Mock(returncode=1, stdout="refused: x", stderr=""))
        with routed(route):
            slice_turn.slice_pending(book, s)
            slice_turn.slice_pending(book, s)
        self.assertEqual(0, len(route.slicer_calls))
        said = [line for line in s.alerts() if "source-gap" in str(line)]
        self.assertEqual(1, len(said))

    def test_a_successful_gap_slice_resets_the_failure_count(self):
        from replan import MAX_REPLANS
        book = tree_with({"id": "T1", "status": "done", "goal": "g", "files": ["a.py"]})
        s = space()
        for _ in range(MAX_REPLANS - 1):
            s.event("slice_finished", task="the sources", rc=2, state="validation_refused")
        s.event("slice_finished", task="the sources", rc=0, state="published")
        s.event("slice_finished", task="the sources", rc=2, state="validation_refused")
        route = router(unittest.mock.Mock(returncode=0, stdout="covered: unchanged", stderr=""))
        with routed(route):
            slice_turn.slice_pending(book, s)
        self.assertEqual(1, len(route.slicer_calls))   # only failures SINCE the success count

    def test_a_provider_refusal_never_counts_toward_the_gap_cap(self):
        from replan import MAX_REPLANS
        book = tree_with({"id": "T1", "status": "done", "goal": "g", "files": ["a.py"]})
        s = space()
        for _ in range(MAX_REPLANS + 1):
            s.event("slice_finished", task="the sources", rc=1, state="(unparsed)")
        route = router(unittest.mock.Mock(returncode=0, stdout="covered: unchanged", stderr=""))
        with routed(route):
            slice_turn.slice_pending(book, s)
        self.assertEqual(1, len(route.slicer_calls))


class OutageTest(unittest.TestCase):
    def test_a_review_outage_spends_no_replans_on_the_target(self):
        book = tree_with({"id": "T1", "status": "needs_slice", "goal": "g",
                          "files": ["a.py"], "triage": "work", "refused_why": "why"})
        s = space()
        route = router(unittest.mock.Mock(
            returncode=2, stdout="review_unavailable: the review did not happen (auth)", stderr=""))
        with routed(route):
            slice_turn.slice_pending(book, s)
        self.assertEqual(1, len(route.slicer_calls))
        self.assertEqual(0, int(book.task("T1").get("replans") or 0))

    def test_a_review_outage_never_counts_toward_the_gap_cap(self):
        from replan import MAX_REPLANS
        book = tree_with({"id": "T1", "status": "done", "goal": "g", "files": ["a.py"]})
        s = space()
        for _ in range(MAX_REPLANS + 1):
            s.event("slice_finished", task="the sources", rc=2, state="review_unavailable")
        route = router(unittest.mock.Mock(returncode=0, stdout="covered: unchanged", stderr=""))
        with routed(route):
            slice_turn.slice_pending(book, s)
        self.assertEqual(1, len(route.slicer_calls))


class PlannerOutageTest(unittest.TestCase):
    def test_a_planner_outage_spends_no_replans_on_the_target(self):
        book = tree_with({"id": "T1", "status": "needs_slice", "goal": "g",
                          "files": ["a.py"], "triage": "work", "refused_why": "why"})
        s = space()
        route = router(unittest.mock.Mock(
            returncode=2, stdout="", stderr="planner_unavailable: no belt answered"))
        with routed(route):
            slice_turn.slice_pending(book, s)
        self.assertEqual(0, int(book.task("T1").get("replans") or 0))

    def test_an_answered_validation_refusal_counts_toward_the_gap_cap(self):
        from replan import MAX_REPLANS
        book = tree_with({"id": "T1", "status": "done", "goal": "g", "files": ["a.py"]})
        s = space()
        for _ in range(MAX_REPLANS):
            s.event("slice_finished", task="the sources", rc=2, state="validation_refused")
        route = router(unittest.mock.Mock(returncode=0, stdout="covered: unchanged", stderr=""))
        with routed(route):
            slice_turn.slice_pending(book, s)
        self.assertEqual(0, len(route.slicer_calls))


class KeptDiffTest(unittest.TestCase):
    def test_the_kept_worktrees_diff_travels_as_evidence(self):
        kept = pathlib.Path(tempfile.mkdtemp())
        (kept / ".git").mkdir()
        book = tree_with({"id": "T1", "status": "needs_slice", "goal": "g",
                          "files": ["a.py"], "triage": "work", "refused_why": "why",
                          "rebuild_from": str(kept)})
        s = space()
        route = router(unittest.mock.Mock(returncode=0, stdout="published: T1.fix", stderr=""))
        read: list[str] = []

        def watching(argv, **kw):
            # the checkout and the temp parent holding it go when the call
            # ends, so the evidence is read as the slicer is handed it
            read.extend(pathlib.Path(a).read_text() for a in argv
                        if str(a).endswith("000-worktree-diff.txt"))
            return route(argv, **kw)

        with routed(watching):
            slice_turn.slice_pending(book, s)
        argv = " ".join(route.slicer_calls[0])
        self.assertIn(".slicer-evidence/000-worktree-diff.txt", argv)
        self.assertIn("deadbeef", "".join(read))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
