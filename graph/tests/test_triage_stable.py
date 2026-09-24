"""What makes two failures the same: the scrub, on its own.

`stable` blanks what a rerun changes — the checkout it ran in, the gate's
scrubbed home, the port of a network address, an elapsed time — and must blank
nothing else. Everything it erases beyond that merges two different failures
into one, which parks a card as a spin for something it never did and denies
the second failure the recovery grant it never spent.

Read through `triage_signatures`, the front door, whichever file holds the
rule.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from triage_signatures import stable

EXPECTED_TESTS = 9
CHECKOUT = "/tmp/graph-tests-9zk/graph-a1b2/task-T1"


class CheckoutTest(unittest.TestCase):
    def test_only_the_checkout_prefix_goes_and_the_path_under_it_stays(self):
        self.assertEqual("<worktree>/pkg/graph-cache/task-one/a.py:12 it said one",
                         stable(f"{CHECKOUT}/pkg/graph-cache/task-one/a.py:12 it said one"))

    def test_two_relative_directories_are_two_failures(self):
        """`pkg/graph-cache/task-one` is a directory somebody wrote, not a
        checkout the loop cut: a greedy parent match ate both and left one
        failure where there were two."""
        self.assertNotEqual(stable(f"{CHECKOUT}/pkg/graph-cache/task-one/a.py failed"),
                            stable(f"{CHECKOUT}/pkg/graph-cache/task-two/a.py failed"))

    def test_the_checkout_is_blanked_wherever_it_was_cut(self):
        self.assertEqual(stable(f"{CHECKOUT}/a.py failed"),
                         stable("/var/tmp/graph-99/task-T1/a.py failed"))

    def test_a_path_written_as_a_uri_is_still_a_path(self):
        """`file://` puts a slash in front of the root, and a rule that reads
        one path boundary too strictly stopped seeing the root at all: two
        reruns of one failure then had two cause keys. The prefix and the path
        under the checkout both survive; the gate's home goes the same way."""
        self.assertEqual("file://<worktree>/pkg/a.py:12 failed",
                         stable("file:///tmp/graph-a/task-T1/pkg/a.py:12 failed"))
        self.assertEqual(stable("file:///tmp/graph-a/task-T1/a.py:12 failed"),
                         stable("file:///tmp/graph-b/task-T1/a.py:12 failed"))
        self.assertEqual(stable("file:///tmp/gate-home-a/x.log is missing"),
                         stable("file:///tmp/gate-home-b/x.log is missing"))

    def test_a_doubled_slash_is_not_where_a_path_begins(self):
        """A path starts at the start of the text, after something that is not
        a name, or after `file://` — and nowhere else. Letting any slash begin
        one made `pkg//graph-cache/task-one` a checkout, and two directories
        somebody wrote came out as one failure. Both suffixes did it."""
        self.assertNotEqual(stable(f"{CHECKOUT}/pkg//graph-cache/task-one/a.py failed"),
                            stable(f"{CHECKOUT}/pkg//graph-cache/task-two/a.py failed"))
        self.assertNotEqual(stable(f"{CHECKOUT}/pkg//gate-home-one/a.py failed"),
                            stable(f"{CHECKOUT}/pkg//gate-home-two/a.py failed"))

    def test_a_uri_keeps_two_lines_of_one_file_apart(self):
        self.assertNotEqual(stable("file:///tmp/graph-a/task-T1/a.py:12 failed"),
                            stable("file:///tmp/graph-a/task-T1/a.py:55 failed"))


class AddressTest(unittest.TestCase):
    def test_a_port_behind_a_url_authority_is_blanked(self):
        for host in ("test-server", "[::1]", "10.0.0.1", "build-host"):
            with self.subTest(host=host):
                self.assertEqual(stable(f"GET http://{host}:40001/check refused"),
                                 stable(f"GET http://{host}:52999/check refused"))

    def test_a_file_and_its_line_are_never_an_address(self):
        self.assertNotEqual(stable("a.py:12 it said one"), stable("a.py:55 it said one"))
        self.assertNotEqual(stable("file:///srv/a.py:12 failed"),
                            stable("file:///srv/a.py:55 failed"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
