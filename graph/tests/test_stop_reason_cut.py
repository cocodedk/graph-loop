"""A stop reason keeps its start and its end: the cause is first, the gate's verdict is last.

The log used to keep the last 2000 characters, and a long gate output pushed the cause out.
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import alert_email
import lean_run
import tmp_root  # noqa: F401
from lean_reason import cut
from test_lean_run import PROFILE, Rig

EXPECTED_TESTS = 5
HEAD = "Fix the red suite. Run run-the-suite, then fix the failure shown below:\n"


class Cut(unittest.TestCase):
    def test_a_reason_of_2000_characters_or_fewer_is_returned_whole(self):
        for size in (0, 1, 1999, 2000):
            with self.subTest(size=size):
                self.assertEqual("x" * size, cut("x" * size))

    def test_2001_characters_keep_the_first_600_a_marker_and_the_last_1400(self):
        text = "".join(chr(33 + number % 90) for number in range(2001))
        self.assertEqual(f"{text[:600]}\n[... 1 characters left out ...]\n{text[-1400:]}", cut(text))

    def test_the_pieces_and_the_count_add_up_to_the_original(self):
        text = "a" * 600 + "b" * 7777 + "c" * 1400
        head, _, rest = cut(text).partition("\n[... 7777 characters left out ...]\n")
        self.assertEqual(len(text), len(head) + 7777 + len(rest))


class Stopped(Rig):
    def stop(self, tail):
        with mock.patch.object(lean_run, "build", self.builder(("ring.py", "a\n"), ("ring.py", "b\n"),
                                                               ("ring.py", "c\n"))), \
                mock.patch.object(lean_run, "masked", lambda ws, command, cwd: (False, tail)), \
                mock.patch.object(alert_email, "send", lambda body, flags, **kw: self.mails.append((kw, body))):
            lean_run.run_feature(self.ws, self.repo, str(self.spec), PROFILE, "profile.md")

    def event(self, kind):
        return next(row for row in self.ws.events() if row["kind"] == kind)

    def test_a_long_reason_is_cut_in_the_log_and_the_repair_event_and_whole_in_the_mail(self):
        tail = "CAUSE" + "g" * 4000 + "END"
        self.stop(tail)
        whole = HEAD + tail
        for kind in ("lean_repair", "lean_stopped"):
            with self.subTest(kind=kind):
                self.assertEqual(cut(whole), self.event(kind)["why"])
        shown = self.event("lean_stopped")["why"]
        self.assertTrue(shown.startswith(HEAD + "CAUSE"))
        self.assertTrue(shown.endswith("ggg" + "END"))
        self.assertIn(f"[... {len(whole) - 2000} characters left out ...]", shown)
        (_, body), = self.mails
        self.assertIn(whole, body)

    def test_a_short_reason_is_whole_in_the_log(self):
        self.stop("FAILED: AmberTest")
        for kind in ("lean_repair", "lean_stopped"):
            with self.subTest(kind=kind):
                self.assertEqual(HEAD + "FAILED: AmberTest", self.event(kind)["why"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
