"""`remember` projects a campaign log onto each card's memory relative.

The note points and never copies: a section names the numbered artifact file,
the event's own time and the commit, and nothing of what the reviewer said or
the gate printed. The same log gives the same bytes, so the note can be thrown
away and rebuilt, and running the command twice writes nothing.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import remember
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]

EXPECTED_TESTS = 11

GATE_OUTPUT = "AssertionError: two != one, and the reviewer must never read this here"
REFUSAL = "the gate greps a line the test prints itself, so it can pass without the work"
COMMIT = "9f1c2ab30d4e5f6a7b8c9d0e1f2a3b4c5d6e7f80"


def vault() -> pathlib.Path:
    """T30, a molecule of two atoms, and T31, a molecule of one."""
    root = pathlib.Path(tempfile.mkdtemp()) / "vault"
    piece = root / "T30"
    piece.mkdir(parents=True)
    (piece / cardfile.HEAD).write_text(
        cardfile.dump({"goal": "a piece", "status": "sliced"}), "utf-8")
    (piece / "01-schema.md").write_text(
        cardfile.dump({"goal": "the field exists", "status": "todo"}), "utf-8")
    (piece / "02-producer.md").write_text(
        cardfile.dump({"goal": "the record carries it", "status": "todo"}), "utf-8")
    lone = root / "T31"
    lone.mkdir()
    (lone / cardfile.HEAD).write_text(
        cardfile.dump({"goal": "a lone piece", "status": "todo"}), "utf-8")
    return root


def call(name: str, number: int = 1, task: str = "T30.schema") -> str:
    """Where the campaign wrote one artifact — the absolute path the log holds,
    built here rather than spelled out, so no machine's name is in a fixture."""
    return str(pathlib.Path(tempfile.gettempdir()) / "campaign" / "calls" / task /
               f"{number:03d}-{name}.txt")


def log() -> list[dict]:
    """One card planned, refused once, built, failing its gate, then kept."""
    return [
        {"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
         "added": ["T30", "T30.schema", "T30.producer", "T31"]},
        {"at": "2026-09-20T07:01:05Z", "kind": "artifact", "task": "T30.schema",
         "name": "contract-answer", "path": call("contract-answer"), "bytes": 77},
        {"at": "2026-09-20T07:01:06Z", "kind": "refused", "task": "T30.schema",
         "step": "contract", "why": REFUSAL},
        {"at": "2026-09-20T07:04:11Z", "kind": "attempt", "task": "T30.schema",
         "account": "work", "outcome": "ok", "counted": True, "cost": 0.4211,
         "tokens": 2912, "failed_gate": False, "purpose": "", "unstarted": False},
        {"at": "2026-09-20T07:05:30Z", "kind": "step", "task": "T30.schema",
         "step": "gate", "seconds": 42.7, "passed": False, "code": 1},
        {"at": "2026-09-20T07:05:31Z", "kind": "artifact", "task": "T30.schema",
         "name": "gate-output", "path": call("gate-output"), "bytes": 4004},
        {"at": "2026-09-20T07:20:00Z", "kind": "accepted", "task": "T30.schema",
         "worktree": "/never/named/here", "commit": COMMIT},
    ]


def written(root: pathlib.Path) -> str:
    """T30.schema's memory, the card every event in `log` is about."""
    return (root / "T30" / "relatives" / "memory-01-schema.md").read_text("utf-8")


class TheNoteIsWhereTheConventionSaysItIs(unittest.TestCase):
    def setUp(self):
        self.root = vault()
        self.counts = remember.write_memory(self.root, log())

    def test_every_card_has_a_memory_relative_in_its_molecules_own_folder(self):
        self.assertEqual(
            ["memory-01-schema.md", "memory-02-producer.md", "memory-molecule.md"],
            sorted(path.name for path in (self.root / "T30" / "relatives").iterdir()))
        self.assertTrue((self.root / "T31" / "relatives" / "memory-molecule.md").exists())

    def test_the_front_matter_names_the_kind_and_links_the_node(self):
        """Read as front matter, not through `cardfile.parse`: the documented
        shape carries a `node:` field AND a `## Node` section, and the parser
        folds both into one key, the section last."""
        front = yaml.safe_load(cardfile.FRONT.match(written(self.root))["front"])
        self.assertEqual({"kind": "memory", "node": "[[T30/01-schema]]"}, front)

    def test_the_node_section_holds_the_link_the_vault_resolves(self):
        self.assertIn("## Node\n\n- [[T30/01-schema]]\n", written(self.root))
        self.assertIn("- [[T30/molecule]]\n",
                      (self.root / "T30" / "relatives" / "memory-molecule.md").read_text("utf-8"))


class ASectionPointsAndNeverCopies(unittest.TestCase):
    def setUp(self):
        self.root = vault()
        remember.write_memory(self.root, log())
        self.text = written(self.root)

    def test_the_gate_section_carries_its_exit_code_its_seconds_and_its_file(self):
        self.assertIn("the gate ran, exit 1", self.text)
        self.assertIn("42.7 seconds", self.text)
        self.assertIn("001-gate-output.txt", self.text)
        self.assertNotIn(GATE_OUTPUT, self.text)

    def test_the_refusal_names_the_numbered_call_and_not_the_reviewers_words(self):
        self.assertIn("001-contract-answer.txt", self.text)
        self.assertNotIn(REFUSAL, self.text)

    def test_the_keep_names_the_commit_and_no_worktree_path(self):
        self.assertIn(COMMIT, self.text)
        self.assertNotIn("/never/named/here", self.text)

    def test_no_machine_path_reaches_the_note_only_the_file_name(self):
        self.assertNotIn(tempfile.gettempdir(), self.text)

    def test_two_gate_runs_in_a_row_each_name_their_own_output(self):
        """The output is written just AFTER the step that ran the gate, so the
        second run's step sits one event from each of the two files. A tie
        broken the other way sends the reader to the previous run's output."""
        root = vault()
        remember.write_memory(root, log()[:5] + [
            {"at": "2026-09-20T07:05:31Z", "kind": "artifact", "task": "T30.schema",
             "name": "gate-output", "path": call("gate-output"), "bytes": 4004},
            {"at": "2026-09-20T07:09:00Z", "kind": "step", "task": "T30.schema",
             "step": "gate", "seconds": 9.14, "passed": True, "code": 0},
            {"at": "2026-09-20T07:09:01Z", "kind": "artifact", "task": "T30.schema",
             "name": "gate-output", "path": call("gate-output", 2), "bytes": 220},
        ])
        green = written(root).split("the gate ran, exit 0")[1]
        self.assertIn("002-gate-output.txt", green)
        self.assertNotIn("001-gate-output.txt", green)


class TheSameLogGivesTheSameBytes(unittest.TestCase):
    def test_running_it_twice_writes_nothing_the_second_time(self):
        root = vault()
        remember.write_memory(root, log())
        before = written(root)
        again = remember.write_memory(root, log())
        self.assertEqual(before, written(root))
        self.assertEqual(0, again["written"])
        self.assertEqual(4, again["unchanged"])

    def test_a_note_thrown_away_is_rebuilt_byte_for_byte(self):
        root = vault()
        remember.write_memory(root, log())
        path = root / "T30" / "relatives" / "memory-01-schema.md"
        before = path.read_bytes()
        path.unlink()
        remember.write_memory(root, log())
        self.assertEqual(before, path.read_bytes())

    def test_the_note_reads_back_as_a_card(self):
        """A relative has a card's shape, so the loop can read it later."""
        root = vault()
        remember.write_memory(root, log())
        for path in sorted((root / "T30" / "relatives").iterdir()):
            cardfile.parse(path.read_text("utf-8"))


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
