"""The builder is told the work is done when the gate passes. It could not run it.

`code_shell` grants the programs the card's gate names, and that derivation is
right — the fourth campaign's Java builder was handed
`Bash(javac *),Bash(java *),Bash(mktemp *)`. Its gate was denied anyway. A
per-program grant authorises a command whose first word is that program; a gate
is a script — `set -e -o pipefail`, then an assignment from `mktemp`, then the
compiler — and no per-program rule describes it. The builder improvised, left
`.class` files in the tree, and the file fence refused the card for exactly the
artifacts its improvising made (2026-09-18).

So the loop writes the gate out as one script and grants that one command. It is
the narrowest thing that can be granted: one word and one fixed path, nothing to
decompose.

The first version wrote it INTO the worktree and exempted it from the file
fence. That is not enough, and the loop's own reviewer said so on the first card
that landed: `worktree.diff` takes the diff with intent-to-add, so an untracked
file is in the diff the reviewer reads, and the keeper commits the index — the
card would have carried the loop's scratch note into the repository, "outside the
contract's file list" (2026-09-18). One file per card outside every worktree has
nothing for the fence, the diff or the keeper to exempt.

Tampering with it buys nothing either way. The VERDICT is run by the driver from
the card's own text (`loop_judge`), never from this copy, so a builder that edits
the script has edited its own scratch note.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from tools import builder_tools, gate_script_path, write_gate_script
from worktree_scope import changed_outside

EXPECTED_TESTS = 6

GATE = 'set -e -o pipefail\nWORK="$(mktemp -d)"\njavac -d "$WORK" src/A.java\njava -cp "$WORK" A\n'


def card(**more: object) -> dict:
    task = {"id": "T1", "goal": "compile it", "files": ["src/A.java"], "gate": GATE,
            "done_when": "the test passes"}
    task.update(more)
    return task


class TheBuilderMayRunItsGate(unittest.TestCase):
    def setUp(self):
        self.tree = pathlib.Path(tempfile.mkdtemp())
        subprocess.run(("git", "init", "-q", str(self.tree)), check=True)
        subprocess.run(("git", "-C", str(self.tree), "commit", "-q", "--allow-empty",
                        "-m", "root"), check=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(self.tree),
                            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})

    def test_the_script_holds_the_gate_byte_for_byte(self):
        where = write_gate_script(card())
        self.assertEqual(GATE, pathlib.Path(where).read_text("utf-8"))

    def test_the_builder_is_granted_that_one_command(self):
        self.assertIn(f"Bash(bash {gate_script_path(card())})",
                      builder_tools(card(), str(self.tree)))

    def test_a_card_with_no_gate_is_granted_nothing_extra(self):
        self.assertNotIn("Bash(bash", builder_tools(card(gate=""), str(self.tree)))

    def test_two_cards_do_not_share_one_script(self):
        self.assertNotEqual(gate_script_path(card()), gate_script_path(card(id="T2")))

    def test_the_script_is_not_in_the_worktree_at_all(self):
        # Not "the fence ignores it": in the tree it reaches the reviewer's diff
        # and the keeper's commit, which no fence exemption covers.
        where = write_gate_script(card())
        self.assertFalse(pathlib.Path(where).is_relative_to(self.tree))
        self.assertEqual([], list(self.tree.glob("**/*.sh")))
        self.assertEqual([], changed_outside(str(self.tree), ["src/A.java"]))

    def test_the_fence_still_catches_what_the_builder_leaves(self):
        write_gate_script(card())
        (self.tree / "build").mkdir()
        (self.tree / "build" / "A.class").write_bytes(b"\xca\xfe\xba\xbe")
        self.assertEqual(["build/A.class"], changed_outside(str(self.tree), ["src/A.java"]))


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
