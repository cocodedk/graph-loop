"""A model call gets a scratch directory of its own, gone when the call ends.

Codex on astra's finding 19: a CODE builder is handed its card's gate as text
(`prompts.py`) and runs it while it works, so a gate that writes
`"$TMPDIR/out.txt"` writes to `/out.txt` when TMPDIR is unset — and to the
driver's own scratch when it is set, where it outlives every call. `run_gate`
already gives a gate its own home; every model call goes through one function
too (`providers._run`), and this is that function's half of the same rule.
"""

from __future__ import annotations

import contextlib
import io
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import providers
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 3


class CallScratchTest(unittest.TestCase):
    def test_a_call_gets_its_own_tmpdir_and_it_is_removed_afterwards(self):
        done = providers._run(["bash", "-c", 'test -d "$TMPDIR" && printf %s "$TMPDIR"'], "")
        given = done.stdout
        self.assertEqual(0, done.returncode, given)          # it existed while the call ran
        self.assertNotEqual(os.environ.get("TMPDIR", ""), given)   # and it was not the driver's
        self.assertFalse(pathlib.Path(given).exists())       # nothing of it outlives the call

    def test_a_directory_the_call_left_unwritable_is_removed_too(self):
        # A build leaves read-only trees behind — a checkout, a package cache.
        # A removal that swallows its own errors leaves the whole scratch on
        # the disk and says nothing, which is the leak again by another road.
        leave_it_locked = ('mkdir -p "$TMPDIR/held" && echo x > "$TMPDIR/held/x" '
                           '&& chmod 500 "$TMPDIR/held" && printf %s "$TMPDIR"')
        done = providers._run(["bash", "-c", leave_it_locked], "")
        given = done.stdout
        self.assertEqual(0, done.returncode, given)
        self.assertFalse(pathlib.Path(given).exists(), "the scratch outlived the call")

    def test_a_scratch_it_cannot_remove_costs_the_answer_nothing(self):
        # A denial no retry beats: the child takes write permission off the
        # directory its scratch sits in, so the last rmdir can never run. The
        # answer is bought and paid for by then — its cost, its session and
        # its text — and a housekeeping fault must not carry it away.
        room = tempfile.mkdtemp(prefix="room-")
        self.addCleanup(os.chmod, room, 0o700)
        self.addCleanup(setattr, tempfile, "tempdir", tempfile.tempdir)
        tempfile.tempdir = room
        said = io.StringIO()
        with contextlib.redirect_stderr(said):
            done = providers._run(["bash", "-c", 'echo kept; chmod 500 "$(dirname "$TMPDIR")"'], "")
        self.assertEqual("kept\n", done.stdout)      # the answer came back
        self.assertIn(room, said.getvalue())         # and what was left behind was named


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
