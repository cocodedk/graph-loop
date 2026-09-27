"""A name the card a leaf waits for creates is there for that leaf.

One plan phase lost three rounds this way. An earlier answer published a card
that `creates: [app/settings.py:def load]` and had not been built yet. A new
atom waited for it and used `app/settings.py:load`. The slicer refused the
atom with "uses unavailable name": it counted only what the new molecule's own
leaves create, and it compared names by exact text. The loop, running the same
atom later, would have let it through, because it counts what the cards ahead
create and the file then holds "def load", which holds "load". Each refusal
spent one of two replans. The way out the planner found was to drop `uses`,
which switches the check off. A name no card promises stays refused.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from contracts import validate
from git_fixture import commit

EXPECTED_TESTS = 5
MAKER = "settings.module"   # published, not built: app/settings.py does not exist yet


class AWaitedForCardCanPromiseAName(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        (self.repo / "spec.md").write_text("# Report\nA report is sent.\n", "utf-8")
        commit(self.repo)
        self.rows = [
            {"id": "settings", "needs": [MAKER], "status": "todo"},
            {"id": MAKER, "needs": [], "status": "todo", "files": ["app/settings.py"],
             "creates": ["app/settings.py:def load"], "sliced_from": "settings"}]

    def check(self, uses: str, needs: list[str] | None = None) -> dict:
        atom = {"name": "sender", "stage": 1, "goal": "send the report",
                "files": ["app/report.py"], "may_add_files": True,
                "needs": [MAKER] if needs is None else needs, "uses": [uses],
                "gate": "set -e -o pipefail\nfalse", "done_when": "the report is sent"}
        made = {"name": "report", "source": ["spec.md:2"], "goal": "a report",
                "why": "nothing sends one", "needs": [], "atoms": [atom]}
        answer = {"result": "MOLECULE", "reason": "one gap", "molecule": made}
        return validate(answer, repo=self.repo, sources=[self.repo / "spec.md"],
                        rows=self.rows)

    def test_a_name_inside_what_the_waited_for_card_creates_is_there(self):
        self.assertEqual("MOLECULE", self.check("app/settings.py:load")["result"])

    def test_the_exact_name_it_creates_is_there(self):
        self.assertEqual("MOLECULE", self.check("app/settings.py:def load")["result"])

    def test_a_name_no_card_creates_is_still_refused(self):
        with self.assertRaisesRegex(ValueError, "unavailable name app/settings.py:save"):
            self.check("app/settings.py:save")

    def test_more_than_the_card_promises_is_refused(self):
        with self.assertRaisesRegex(ValueError, "unavailable name"):
            self.check("app/settings.py:def load(path)")

    def test_a_card_the_leaf_does_not_wait_for_promises_it_nothing(self):
        with self.assertRaisesRegex(ValueError, "unavailable name app/settings.py:load"):
            self.check("app/settings.py:load", needs=[])


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
