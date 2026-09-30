"""A change that carries leftover files is sent back before the suite runs, and the reviewer must name a file the
spec does not call for. The gate checks that what was built works; this checks that nothing else came with it."""

import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lean_diff
import tmp_root  # noqa: F401
from providers import Outcome
from test_lean_run import ACCEPT, Rig

EXPECTED_TESTS = 3


def new(path):
    return f"diff --git a/{path} b/{path}\nnew file mode 100644\nindex 0000000..e69de29\n--- /dev/null\n+++ b/{path}\n"


def changed(path):
    return f"diff --git a/{path} b/{path}\nindex 1111111..2222222 100644\n--- a/{path}\n+++ b/{path}\n"


class Finds(unittest.TestCase):
    def test_only_new_files_with_leftover_names_are_leftovers(self):
        diff = "".join(new(p) for p in ("ring.py", "ring.py.orig", "src/x.rej", "notes.bak", "y.swp", "z~", "t.tmp",
                                        "a/.DS_Store", "m.pyc", "pkg/__pycache__/m.cpython-314.pyc",
                                        "web/node_modules/left-pad/index.js", "docs/orig-plan.md")) \
            + changed("old.bak") + changed("keep.py")
        self.assertEqual(["ring.py.orig", "src/x.rej", "notes.bak", "y.swp", "z~", "t.tmp", "a/.DS_Store", "m.pyc",
                          "pkg/__pycache__/m.cpython-314.pyc", "web/node_modules/left-pad/index.js"],
                         lean_diff.leftovers(diff))
        self.assertEqual([], lean_diff.leftovers(""))


class Sent(Rig):
    def test_a_build_that_leaves_a_stray_file_is_sent_back_with_it_named_and_lands_once_it_is_gone(self):
        calls = []

        def build(ws, task, prompt, tree, resume="", effort=""):
            calls.append(prompt)
            work = pathlib.Path(tree.path)
            if len(calls) == 1:
                (work / "ring.py").write_text("amber\n")
                (work / "ring.py.orig").write_text("old\n")
            else:
                (work / "ring.py.orig").unlink()
            return Outcome("ok", session="s1")
        self.assertTrue(self.run_it(build, suites=(True,)))
        self.assertEqual(2, len(calls))
        self.assertIn("leftover files", calls[1])
        self.assertIn("ring.py.orig", calls[1])
        listed = subprocess.run(("git", "-C", self.repo, "ls-tree", "--name-only", "lean/rest-ring"),
                                capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(["a.py", "ring.py"], listed)
        self.assertEqual(1, len(self.suites))                # the first round never reached the suite

    def test_the_reviewer_must_name_a_file_the_spec_does_not_call_for(self):
        self.run_it(self.builder(("ring.py", "amber\n")), reviews=(ACCEPT,))
        self.assertIn("a file the spec does not call for that nothing uses", self.reviews[0])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
