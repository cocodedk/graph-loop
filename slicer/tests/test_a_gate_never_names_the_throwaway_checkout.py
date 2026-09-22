"""A card's gate never names the directory the planner read.

The slicer plans against a throwaway copy of the campaign tip (`clean_tree`),
and the prompt used to hand that copy's path over as `Repository:`. One card
in eight of run 6 did the reasonable thing with it and opened its gate with
`cd /tmp/slice-repo-2dd3xish/tree`. That directory is gone before any builder
runs, so the gate would have judged nothing — and the card carried a machine
path into a tracked note, which is exactly what the loop's own repository has
a scrub check to keep out.

The graph loop's doctor catches it, a published card and a repair round later.
This is that round: the prompt no longer hands the path over, and a gate that
names it anyway is refused before the card is written.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from asking import prompt
from contracts import validate
from git_fixture import commit

EXPECTED_TESTS = 4
# Run 6's card, verbatim but for the checkout path, which is this test's own.
RUN_6 = ("set -e -o pipefail\ncd {repo}\nOUT=$(mktemp -d)\n"
         'javac -d "$OUT" src/FetchFailureMessage.java test/FetchFailureMessageTest.java\n'
         'java -cp "$OUT" FetchFailureMessageTest')


class AGateNeverNamesTheCheckout(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        (self.repo / "specs").mkdir()
        (self.repo / "specs" / "greeting.md").write_text("# Greeting\nIt is returned.\n", "utf-8")
        (self.repo / "app.py").write_text("def read():\n    return 1\n", "utf-8")
        commit(self.repo)

    def check(self, gate: str) -> dict:
        made = {"name": "greeting", "source": ["specs/greeting.md:2"],
                "goal": "return a greeting", "why": "the function is absent", "needs": [],
                "atoms": [], "files": ["app.py"], "gate": gate,
                "done_when": "the greeting test passes"}
        return validate({"result": "MOLECULE", "reason": "one gap", "molecule": made},
                        repo=self.repo, sources=[self.repo / "specs"], rows=[])

    def test_run_6s_own_gate_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            self.check(RUN_6.format(repo=self.repo))
        self.assertIn("throwaway copy", str(caught.exception))

    def test_the_same_gate_without_the_cd_is_fine(self):
        answered = self.check(RUN_6.format(repo=".").replace("cd .\n", ""))
        self.assertEqual("MOLECULE", answered["result"])

    def test_the_path_alone_is_enough_without_a_cd(self):
        """`cd` is one way to name it; a classpath or a source argument is
        another, and the refusal is about the path, not the verb."""
        with self.assertRaises(ValueError):
            self.check(f"set -e -o pipefail\npython3 {self.repo}/app.py")

    def test_the_planner_is_never_handed_the_path(self):
        said = prompt(self.repo, [self.repo / "specs" / "greeting.md"], [])
        self.assertNotIn(str(self.repo), said)
        self.assertIn("every path in a card is relative", said)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
