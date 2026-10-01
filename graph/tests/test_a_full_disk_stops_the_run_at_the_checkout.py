"""A full temp folder must not end the run silently while the feature's checkout is cut (issue #286).

`git clone` into a full folder fails half way, after writing part of the checkout. The run must stop with
a `lean_stopped` event and a mail that say why, leave no half checkout behind, and never call the builder.
Git is real except the clone, which writes one file and fails (`test_lean_run.Rig`).
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import worktree
from test_lean_run import Rig

EXPECTED_TESTS = 2
FULL = "fatal: sha1 file './.git/index.lock' write error: Disk quota exceeded"
real_git = worktree._git


class FullTempFolder(Rig):
    def stop_while_cutting(self):
        half = []

        def git(root, *args):
            if "clone" in args:                    # what a full disk does: part of the checkout, then the error
                target = pathlib.Path(args[-1])
                target.mkdir(parents=True)
                (target / "partial").write_text("half")
                half.append(target)
                raise RuntimeError(f"git {' '.join(args)}: error: unable to write file x\n{FULL}")
            return real_git(root, *args)
        with mock.patch.object(worktree, "_git", git):
            url = self.run_it(self.builder(("ring.py", "amber\n")))
        return url, half

    def test_the_run_stops_with_an_event_and_a_mail_that_say_why(self):
        url, _ = self.stop_while_cutting()
        self.assertEqual("", url)
        stopped = next(row for row in self.ws.events() if row["kind"] == "lean_stopped")
        self.assertIn("Disk quota exceeded", stopped["why"])
        self.assertIn("TMPDIR", stopped["why"])
        self.assertEqual([], self.prompts)         # the builder was never called
        (_, body), = self.mails
        self.assertIn("Disk quota exceeded", body)
        self.assertIn("TMPDIR", body)

    def test_no_half_checkout_is_left_behind(self):
        _, half = self.stop_while_cutting()
        self.assertEqual(1, len(half))
        self.assertFalse(half[0].exists())
        self.assertFalse(half[0].parent.exists())  # nor the folder the checkout was cut in


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())   # the two above and this one


if __name__ == "__main__":
    unittest.main()
