"""The builder was granted one command to run its gate and never told its path.

`code_shell` grants `Bash(bash <path>)` and `write_gate_script` puts the gate
there, byte for byte, but the prompt said only "Prove it with: <the gate text>".
So the builder read a script and tried to run it as commands: a per-program grant
authorises a command whose first word is that program, and a gate is a script, so
the compound line was denied. It improvised a compile into the tree, and the file
fence then refused the card for exactly the output the improvising made
(2026-09-18).

The grant, the file and the instruction are three halves of one thing, and this
branch shipped the first two. Reported as the fence's ignore list knowing only
Python and Node; that list is a separate wart and not what happened here.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from gate_script import gate_script_path
from prompts import build_prompt
from tools import builder_tools

EXPECTED_TESTS = 5

GATE = 'set -e -o pipefail\nWORK="$(mktemp -d)"\njavac -d "$WORK" src/A.java\njava -cp "$WORK" A\n'


def card(**more: object) -> dict:
    task = {"id": "T1", "goal": "compile it", "files": ["src/A.java"], "gate": GATE,
            "done_when": "the test passes"}
    task.update(more)
    return task


class TheBuilderCanFindItsGate(unittest.TestCase):
    def test_running_the_gate_is_optional_even_after_a_denied_command(self):
        for extra in ({}, {"gate": ""}, {"gate_has_side_effects": True}, {"rejections": ["old failure"]}):
            said = build_prompt(card(**extra))
            self.assertIn("You do not need to run the gate yourself", said)
            self.assertIn("the loop runs it after you finish", said)
            self.assertIn("if a command is denied, finish the edit and end normally", said)
            self.assertIn("do not stop as BLOCKED for that", said)

    def test_the_prompt_names_the_path_it_was_granted(self):
        said = build_prompt(card())
        self.assertIn(f"bash {gate_script_path(card())}", said)

    def test_the_path_is_the_one_the_grant_allows(self):
        # the prompt and the allowlist must not drift apart: one source for both
        granted = builder_tools(card(), "/tmp/tree")
        self.assertIn(f"Bash(bash {gate_script_path(card())})", granted)
        self.assertIn(f"bash {gate_script_path(card())}", build_prompt(card()))

    def test_it_says_why_improvising_is_what_fails(self):
        said = build_prompt(card())
        self.assertIn("does not authorise the script", said)
        self.assertIn("outside its files", said)

    def test_a_card_with_no_gate_is_told_nothing(self):
        self.assertNotIn("Run it with:", build_prompt(card(gate="")))


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
