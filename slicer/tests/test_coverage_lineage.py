"""What the coverage reviewer was shown about replacement is digested too.

Codex's review: `replacements` reads `sliced_from` to tell the reviewer what
replaced each sliced molecule, but `sliced_from` was not among the digested
contract fields. So a piece could stop declaring itself T12's replacement — or
start declaring itself another card's — and the accepted coverage stood, over a
listing that would now read differently.

The rule has been the same since the digest was written: what the reviewer
reads is what is hashed. The replacement listing is decided entirely by `id`,
`status` and `sliced_from`, and now all three are digested.
"""

from __future__ import annotations

import copy
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import slicer_state
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 2

REVIEWED = [
    {"id": "T12", "status": "sliced", "goal": "the replaced one",
     "source": ["specs/greeting.md:1"], "needs": ["T1"]},
    {"id": "T18", "status": "todo", "goal": "the replacement", "sliced_from": "T12",
     "files": ["app.py"], "gate": "set -e -o pipefail\nfalse",
     "done_when": "the greeting test passes"},
]


def accepted_for(rows: list[dict]) -> bool:
    """A coverage record closed over REVIEWED, then asked about `rows`."""
    repo = pathlib.Path(tempfile.mkdtemp())
    backlog, specs = repo / "backlog", repo / "specs"
    backlog.mkdir(); specs.mkdir()
    source = specs / "greeting.md"
    source.write_text("## Goal\nReturn a greeting.\n", "utf-8")
    slicer_state.close(backlog, [source], "accepted", repo, REVIEWED)
    assert slicer_state.accepted(backlog, REVIEWED)
    return slicer_state.accepted(backlog, rows)


class LineageTest(unittest.TestCase):
    def test_a_replacement_that_stops_declaring_its_parent_makes_coverage_stale(self):
        orphaned = copy.deepcopy(REVIEWED)
        del orphaned[1]["sliced_from"]

        self.assertFalse(accepted_for(orphaned))

    def test_a_replacement_moved_to_another_parent_makes_coverage_stale(self):
        moved = copy.deepcopy(REVIEWED)
        moved[1]["sliced_from"] = "T99"

        self.assertFalse(accepted_for(moved))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
