"""The lean loop's reviewer runs at the effort the owner set (2026-09-25: high)."""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_run
import tmp_root  # noqa: F401


class LeanReviewEffortTest(unittest.TestCase):
    def test_the_diff_review_asks_for_high_effort(self):
        calls = []

        def codex(binary, prompt, **kwargs):
            calls.append(kwargs)
            return "outcome"
        with mock.patch.object(lean_run.review, "codex", codex):
            lean_run.judge(mock.Mock(), "feature", "spec", "diff", "/tmp")
        self.assertEqual("high", calls[0]["effort"])


if __name__ == "__main__":
    unittest.main()
