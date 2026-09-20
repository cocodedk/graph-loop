"""`main` hands `run_answer` a cut checker when it has a campaign, and none without.

Two tests prove only what is passed to `run_answer`. The third calls the checker
it was given, with the decisions model stubbed, to show it reaches that model with
the target card and leaves its record in the campaign, and that the repository is
the checker's space; what the check decides is
`cut_check`'s own test.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import cut_states
import intelligence
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

import slicer

EXPECTED_TESTS = 3
CARD = {"id": "T1", "goal": "return a greeting"}


def run_main(*extra: str, target: str = "") -> dict:
    """Run `main` with `run_answer` patched; return the kwargs it was called with."""
    repo = pathlib.Path(tempfile.mkdtemp())
    backlog, specs = repo / "backlog", repo / "specs"
    backlog.mkdir(); specs.mkdir()
    (specs / "greeting.md").write_text("## Goal\nReturn a greeting.\n", "utf-8")
    (repo / "answer.json").write_text("{}", "utf-8")
    argv = ["--repo", str(repo), "--backlog", str(backlog), "--source", "specs/greeting.md",
            "--answer", str(repo / "answer.json"), *extra]
    with mock.patch.object(slicer, "run_answer", return_value=("published", "ok")) as run, \
            mock.patch.object(intelligence, "CAMPAIGN", intelligence.CAMPAIGN):
        if target:      # a card the backlog holds, past the recovery a real one goes through
            with mock.patch.object(slicer, "Backlog") as book, \
                    mock.patch.object(slicer, "assert_wall"), \
                    mock.patch.object(slicer, "recover", return_value=(None, None)):
                book.return_value.tasks.return_value = [CARD]
                slicer.main([*argv, "--target", target])
        else:
            slicer.main(argv)
    run.assert_called_once()
    return run.call_args.kwargs


class MainCutCheckTest(unittest.TestCase):
    def test_a_campaign_gets_a_callable_checker(self):
        campaign = tempfile.mkdtemp()
        self.assertTrue(callable(run_main("--campaign", campaign).get("checker")))

    def test_no_campaign_means_no_checker(self):
        self.assertIsNone(run_main().get("checker"))

    def test_the_checker_asks_the_model_about_the_target_card_and_records_it(self):
        campaign = pathlib.Path(tempfile.mkdtemp())
        cut_states.switch(campaign, "observe", "test")
        model = mock.Mock(return_value=SimpleNamespace(ok=False, answers={}, why="stub"))
        with mock.patch.object(slicer, "decide", model), \
                mock.patch.object(slicer, "make_checker", wraps=slicer.make_checker) as made:
            passed = run_main("--campaign", str(campaign), target="T1")
            passed["checker"]({"atoms": [{"id": "a"}, {"id": "b"}]})
        self.assertEqual(passed["repo"], made.call_args.args[1])   # the space is the repository
        self.assertTrue(model.called)                       # the ask ran, it did not fail first
        self.assertTrue(all(call.args[0].get("wall") == CARD
                            for call in model.call_args_list if "atom" in call.args[0]))
        events = [json.loads(line) for part in campaign.glob("events*.jsonl")
                  for line in part.read_text("utf-8").splitlines()]
        self.assertIn("cut_asked", [row["kind"] for row in events])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)
