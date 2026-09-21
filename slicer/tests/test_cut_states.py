"""The cut state is off until switched, and every switch is kept in order."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import yaml  # type: ignore[import-untyped]
from cut_states import load, switch


def history_of(campaign: pathlib.Path) -> list:
    return yaml.safe_load((campaign / "cut-states.yaml").read_text("utf-8"))["history"]


class CutStates(unittest.TestCase):
    def setUp(self):
        self.campaign = pathlib.Path(tempfile.mkdtemp())

    def test_absent_file_is_off(self):
        self.assertEqual(load(self.campaign), "off")

    def test_switch_is_read_back(self):
        switch(self.campaign, "observe", "someone")
        self.assertEqual(load(self.campaign), "observe")

    def test_history_keeps_earlier_entries_in_order(self):
        switch(self.campaign, "observe", "someone")
        first = history_of(self.campaign)[0]
        switch(self.campaign, "act", "someone else")
        self.assertEqual(load(self.campaign), "act")
        history = history_of(self.campaign)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0], first)
        self.assertEqual([h["to"] for h in history], ["observe", "act"])
        for entry in history:
            self.assertEqual(sorted(entry), ["at", "by", "to"])
            self.assertTrue(isinstance(entry["at"], str) and entry["at"])


if __name__ == "__main__":
    unittest.main()
