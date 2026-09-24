"""A missing machine toolchain spends no card round, even at the round cap."""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import provider_words
from gates import GateResult
from keep import CombinedGateFailed
from loop_judge import _keep, judge
from test_loop import Fakes, loop_for, task
from worktree import Worktree

SDK = ("Could not determine the dependencies of task ':app:testDebugUnitTest'.\n"
       "> SDK location not found. Define a valid SDK location with an ANDROID_HOME "
       "environment variable or by setting the sdk.dir path in local.properties.")


class GateEnvironmentTest(unittest.TestCase):
    def test_every_named_toolchain_phrase_is_recognized(self):
        for phrase in (SDK, "ANDROID_HOME is unset", "JAVA_HOME is invalid",
                       "javac: command not found", "./gradlew: No such file or directory",
                       "Unable to locate a Java Runtime", "could not find tools.jar"):
            with self.subTest(phrase=phrase):
                self.assertTrue(provider_words.environment_hint(phrase, "./gradlew test"))

    def test_a_missing_fixture_is_not_a_missing_runner(self):
        for phrase in ("fixtures/input.json: No such file or directory",
                       "AssertionError: expected 2, got 1",
                       "FileNotFoundError: [Errno 2] No such file or directory: 'gradlew'"):
            with self.subTest(phrase=phrase):
                self.assertFalse(provider_words.environment_hint(phrase, "./gradlew test"))

    def test_red_first_stops_before_review_or_build_and_keeps_the_card(self):
        fakes = Fakes()
        loop, book, space = loop_for(task(gate="./gradlew test"), fakes)
        before = book.task("T1")
        with mock.patch("gates.run_gate", return_value=GateResult(1, SDK + "\nnoise" * 1000)):
            out = loop.run_task(book.task("T1"))
        self.assertEqual("environment", out.state)
        self.assertEqual(before, book.task("T1"))
        self.assertEqual([], fakes.calls)
        self.assertEqual(0, space.attempts("T1"))

    def test_post_build_failure_leaves_status_and_rounds_unchanged(self):
        loop, book, space = loop_for(task(rebuild_round=2, gate_rounds=1), Fakes())
        tree = Worktree(loop.repo, "T1").create()
        before = book.task("T1")
        with mock.patch("loop_judge.run_gate", return_value=GateResult(1, SDK)):
            out = judge(loop, before, tree, "./gradlew test", 2)
        self.assertEqual("environment", out.state)
        self.assertEqual(before, book.task("T1"))
        self.assertFalse(space.needs_slice("T1"))
        self.assertEqual([], [row for row in space.events()
                              if row["kind"] in ("attempt", "failed", "rejected")])

    def test_combined_gate_failure_does_not_charge_the_card(self):
        loop, book, space = loop_for(task(rebuild_round=2), Fakes())
        tree = Worktree(loop.repo, "T1").create()
        loop.keeper = mock.Mock()
        loop.keeper.keep.side_effect = CombinedGateFailed(SDK, gate="./gradlew test")
        out = _keep(loop, book.task("T1"), tree, 2)
        self.assertEqual("environment", out.state)
        self.assertEqual("todo", book.task("T1")["status"])
        self.assertEqual(2, book.task("T1")["rebuild_round"])
        self.assertFalse(space.needs_slice("T1"))

    def test_an_ordinary_test_failure_still_charges_a_round(self):
        loop, book, space = loop_for(task(), Fakes())
        tree = Worktree(loop.repo, "T1").create()
        with mock.patch("loop_judge.run_gate", return_value=GateResult(1, "AssertionError: 1 != 2")):
            out = judge(loop, book.task("T1"), tree, "./gradlew test", 0)
        self.assertEqual("failed", out.state)
        self.assertEqual(1, book.task("T1")["rebuild_round"])
        self.assertEqual(1, space.attempts("T1"))

    def test_a_passing_gate_can_mention_the_environment(self):
        loop, book, _ = loop_for(task(files=[], gate="printf 'ANDROID_HOME is optional'"), Fakes())
        self.assertEqual("done", loop.run_task(book.task("T1")).state)
