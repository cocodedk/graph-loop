"""A write killed mid-line leaves a partial event; the log still reads.

The disk filled on 2026-09-03 and cut one event in half. Every reader parsed
every line, so the campaign's whole memory raised instead of answering, until a
person deleted the line by hand and wrote a `log_truncated` event in its place
(commit a1bb30bf). The rules under test: a partial LAST line is tolerated and
its bytes are kept in the log itself, it is recorded once and not again, the
next append does not glue onto it, a row that lost only its newline stays the
event it is, and corruption earlier in the log is still an error.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from workspace import EVENTS, Workspace

EXPECTED_TESTS = 7

HALF = '{"at": "2026-09-03T18:55:57Z", "kind": "id'   # what the full disk left


def fresh() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog="backlog.yaml")


def cut(space: Workspace, text: str = HALF) -> None:
    """Append what a killed write leaves behind: no trailing newline."""
    with (space.root / EVENTS).open("ab") as handle:
        handle.write(text.encode("utf-8"))


class TruncatedTailTest(unittest.TestCase):
    def test_a_partial_last_line_is_read_and_its_bytes_are_kept(self):
        space = fresh()
        space.event("started", task="T1")
        cut(space)
        rows = space.events()
        self.assertEqual(["init", "started", "log_truncated"], [row["kind"] for row in rows])
        self.assertEqual(HALF, rows[-1]["text"])

    def test_the_partial_line_is_recorded_once_however_often_the_log_is_read(self):
        space = fresh()
        cut(space)
        space.events()
        space.event("started", task="T1")
        fresh_reader = Workspace(space.root)          # no cache of its own
        rows = fresh_reader.events()
        self.assertEqual(1, sum(1 for row in rows if row["kind"] == "log_truncated"))

    def test_the_next_event_does_not_glue_onto_a_partial_line(self):
        space = fresh()
        cut(space)
        space.event("started", task="T1")
        self.assertEqual(["init", "log_truncated", "started"],
                         [row["kind"] for row in space.events()])

    def test_a_row_that_lost_only_its_newline_stays_the_event_it_is(self):
        space = fresh()
        cut(space, json.dumps({"at": "2026-09-03T18:55:57Z", "kind": "accepted", "task": "T1"}))
        self.assertEqual(["init", "accepted"], [row["kind"] for row in space.events()])
        space.event("started", task="T1")
        self.assertEqual(["init", "accepted", "started"],
                         [row["kind"] for row in space.events()])

    def test_a_repair_that_cannot_finish_leaves_the_partial_bytes_alone(self):
        """The disk that cut the line is usually still full, so the repair
        itself can die halfway. Both ends of the window are tried: composing
        the replacement, and the write that puts it on the platter — where a
        full disk really raises. Whichever end fails, the bytes must still be
        on disk for the next attempt to keep."""
        for seam in ("workspace_log._now", "workspace_log.os.fsync"):
            with self.subTest(seam=seam):
                space = fresh()
                space.event("started", task="T1")
                cut(space)
                before = (space.root / EVENTS).read_bytes()
                with mock.patch(seam, side_effect=OSError(28, "No space left")), \
                        self.assertRaises(OSError):
                    space.events()
                self.assertEqual(before, (space.root / EVENTS).read_bytes())
                self.assertEqual(["init", "started", "log_truncated"],   # the next attempt keeps them
                                 [row["kind"] for row in Workspace(space.root).events()])

    def test_a_corrupt_line_that_is_not_the_last_is_an_error(self):
        space = fresh()
        cut(space, '{"at": "2026-09-03T18:55:57Z", "kind": "id\n')   # complete line, broken JSON
        space.event("started", task="T1")
        with self.assertRaises(json.JSONDecodeError):
            space.events()


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
