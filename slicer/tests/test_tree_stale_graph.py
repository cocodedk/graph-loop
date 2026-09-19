"""The graph is checked again at publication, not only before the paid review.

astra's round-2 review, finding 7: `slicer.run_answer` validates the answer
(`contracts.validate` → `slicer_law.assert_order`) against the backlog as it
was, then pays for a progress review, and only then publishes. Another writer
can land `M.a` in that window, so the molecule `M` publishes an atom whose
derived id already belongs to somebody else. The lock the publish holds is the
only place the whole prospective graph is still true.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
DRIVE_LIB = HERE.parent / "drive" / "lib"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(DRIVE_LIB))
from test_tree import atom, task
from tree import publish

EXPECTED_TESTS = 1


class StaleGraphTest(unittest.TestCase):
    def test_an_id_that_appeared_since_validation_stops_the_publish(self):
        root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
        root.mkdir()
        publish(root, task("greeting.reader"))       # another writer, mid-review
        with self.assertRaisesRegex(ValueError, "greeting.reader already exists"):
            publish(root, task("greeting", atoms=[atom("reader", 1)]))
        self.assertFalse((root / "greeting").exists())


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
