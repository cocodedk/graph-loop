"""A fresh tree is on the card before the builder is paid: a driver that dies
mid-build (the full disk of 2026-09-03 took one $2.73 build this way) resumes
on that tree instead of cutting another (astra's review of 2026-09-08, finding 3)."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 4


class TreeRecordedFirstTest(unittest.TestCase):
    def test_the_card_names_the_tree_before_the_builder_is_paid(self):
        fakes = Fakes()
        loop, book, space = loop_for(task(), fakes)
        seen: dict = {}

        def dies(prompt, **kw):
            seen["card"] = dict(book.task("T1"))       # what the card says at the moment of the call
            raise OSError(28, "No space left on device")

        loop.build = dies
        with self.assertRaises(OSError):
            loop.run_task(book.task("T1"))
        cut = [r for r in space.events() if r["kind"] == "worktree" and r.get("task") == "T1"]
        self.assertEqual(1, len(cut))
        self.assertEqual(cut[0]["path"], seen["card"].get("rebuild_from"))

    def test_a_death_before_red_first_records_no_tree_so_the_retry_proves_red(self):
        import loop_evidence
        fakes = Fakes()
        loop, book, space = loop_for(task(), fakes)
        real = loop_evidence.prove_red
        loop_evidence.prove_red = lambda *a: (_ for _ in ()).throw(OSError(28, "No space left on device"))
        try:
            with self.assertRaises(OSError):
                loop.run_task(book.task("T1"))
        finally:
            loop_evidence.prove_red = real
        self.assertFalse(book.task("T1").get("rebuild_from"))   # nothing paid: nothing to resume
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        kinds = [r["kind"] for r in space.events() if r.get("task") == "T1"]
        self.assertNotIn("skipped_red_first", kinds)
        ran = [r for r in space.events() if r["kind"] == "step" and r.get("step") == "red_first"]
        self.assertEqual([True, False], [bool(r.get("error")) for r in ran])   # died once, then ran


class ReplacementTreeTest(unittest.TestCase):
    def test_a_replacement_tree_is_no_different(self):
        import loop_evidence
        fakes = Fakes()
        loop, book, space = loop_for(task(rebuild_round=1, rebuild_from="", contract_seen=""), fakes)
        real = loop_evidence.prove_red
        loop_evidence.prove_red = lambda *a: (_ for _ in ()).throw(OSError(28, "No space left on device"))
        try:
            with self.assertRaises(OSError):
                loop.run_task(book.task("T1"))
        finally:
            loop_evidence.prove_red = real
        self.assertFalse(book.task("T1").get("rebuild_from"))
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertNotIn("skipped_red_first", [r["kind"] for r in space.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
