"""The dashboard shows how many turns each spec's builds took. The Claude answer carries `num_turns` for the call
(a resumed call reports its own turns, not the session's); the outcome keeps it, the build's attempt event records
it, and the project view adds the spec's total after the date."""

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lean_run
import project_cost
import project_view
import providers
import tmp_root  # noqa: F401
from loops_ps import Loop
from providers import Outcome, claude
from test_project_cost import build, project, started, write
from test_project_marks import git, using
from test_providers import fake
from workspace import Workspace

EXPECTED_TESTS = 5


def answer(**fields):
    binary = fake("cat > /dev/null; echo '" + json.dumps({"result": "ok", "total_cost_usd": 0.5, "permission_denials": [],
                                                          "usage": {"input_tokens": 1, "output_tokens": 1}, **fields}) + "'")
    return claude(binary, "prompt", account="work")


class Recorded(unittest.TestCase):
    def test_the_outcome_keeps_the_calls_turns_and_ignores_what_is_not_a_number(self):
        self.assertEqual(86, answer(num_turns=86).turns)
        for odd in ({}, {"num_turns": None}, {"num_turns": "86"}, {"num_turns": True}):
            with self.subTest(odd=odd):
                self.assertIsNone(answer(**odd).turns)

    def test_the_build_attempt_records_its_turns_and_others_record_none(self):
        ws = Workspace(tempfile.mkdtemp())
        with mock.patch.object(providers, "claude", return_value=Outcome("ok", cost=1.0, turns=7)):
            lean_run.build(ws, {"id": "x", "gate": "true"}, "build it", mock.Mock(path="/tmp"))
        (row,) = [r for r in ws.events() if r["kind"] == "attempt"]
        self.assertEqual(7, row["turns"])
        ws.attempt("y", account="a", kind="ok")                          # a call with no turns adds no field
        self.assertNotIn("turns", next(r for r in ws.events() if r.get("task") == "y"))


class Shown(unittest.TestCase):
    def test_the_total_of_the_builds_turns_follows_the_date_and_is_left_off_without_data(self):
        root = project(**{"01-a.md": "", "02-b.md": ""})
        write(root, "events.jsonl", [started("01-a"), {**build("01-a", 1.5), "turns": 30},
                                     {**build("01-a", 2.5), "turns": 56},
                                     {**build("01-a", 9.0, "review"), "turns": 500},           # only builds count
                                     {"kind": "lean_published", "task": "01-a", "at": "2026-09-30T07:33:21Z"},
                                     started("02-b"), build("02-b", 0.5)])                     # no turns recorded
        self.assertEqual({"01-a": 86}, project_cost.card_turns(str(root)))
        with using(git(["feat(01-a): x"])):
            lines = project_view.report(str(root), [], 0, None).splitlines()
        self.assertIn("✔ built     01-a  $2.50  2026-09-30  86t", lines)
        self.assertIn("· waiting   02-b  $0.50", lines)


def call(task, purpose, **fields):
    return {"kind": "lean_call_started", "task": task, "purpose": purpose, **fields}


class Lines(unittest.TestCase):
    def log(self, root):
        write(root, "events.jsonl", [
            started("01-a"), call("01-a", "build", model="claude-sonnet-5-5"), {**build("01-a", 2.5), "turns": 86},
            call("01-a", "review", model="gpt-6-sol"),                                # a review's model is not the builder's
            call("01-a", "build", model="claude-opus-5-5"),                            # the last build call wins
            {"kind": "lean_published", "task": "01-a", "at": "2026-09-30T07:33:21Z"},
            started("02-b"), call("02-b", "build"), build("02-b", 0.5)])               # an older event: no model

    def test_a_spec_line_shows_the_model_of_its_last_build_after_the_turns(self):
        root = project(**{"01-a.md": "", "02-b.md": ""})
        self.log(root)
        self.assertEqual({"01-a": "opus-5-5"}, project_cost.card_models(str(root)))
        with using(git(["feat(01-a): x"])):
            lines = project_view.report(str(root), [], 0, None).splitlines()
        self.assertIn("✔ built     01-a  $2.50  2026-09-30  86t  opus-5-5", lines)
        self.assertIn("· waiting   02-b  $0.50", lines)

    def test_a_running_specs_loop_line_shows_its_turns_so_far(self):
        root = project(**{"01-a.md": "", "02-b.md": ""})
        self.log(root)
        loop = Loop(1, 100, "p", "01-a", str(root / "scratchpad" / "lean"))
        with using(git([])):
            report = project_view.report(str(root), [loop], 1_900_000_000, None)
        self.assertIn("86t", next(line for line in report.splitlines() if line.startswith("  loop:")))
        other = Loop(1, 100, "p", "02-b", str(root / "scratchpad" / "lean"))
        with using(git([])):
            report = project_view.report(str(root), [other], 1_900_000_000, None)
        self.assertNotIn("t\n", next(line for line in report.splitlines() if line.startswith("  loop:")) + "\n")


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
