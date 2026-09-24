"""The source digest is the same in any checkout root and news when a file moves."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from slicer_state import digest

EXPECTED_TESTS = 2


def checkout(rel_path: str, body: str) -> tuple[pathlib.Path, pathlib.Path]:
    root = pathlib.Path(tempfile.mkdtemp())
    source = root / rel_path
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(body, "utf-8")
    return root, source


class DigestTest(unittest.TestCase):
    def test_two_checkout_roots_agree_on_the_same_sources(self):
        a_root, a = checkout("specs/greeting.md", "## Goal\n")
        b_root, b = checkout("specs/greeting.md", "## Goal\n")
        self.assertEqual(digest([a], a_root), digest([b], b_root))

    def test_a_moved_file_with_the_same_bytes_is_news(self):
        a_root, a = checkout("specs/greeting.md", "## Goal\n")
        b_root, b = checkout("specs/old/greeting.md", "## Goal\n")
        self.assertNotEqual(digest([a], a_root), digest([b], b_root))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
