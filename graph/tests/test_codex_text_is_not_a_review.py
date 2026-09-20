"""A decision is not a verdict, so the transport must not grade the answer.

`providers.codex` is a REVIEW interface: it reads the reply for ACCEPT or
REJECT and calls everything else malformed. A perfectly good drop answer sent
through it comes back as a fault, so the decider would spend its retry and its
fallback on every well-formed decision it ever gets (astra's provider trap,
section C). The first test below is that trap, live.

`codex_text` is the same call with the verdict decoding taken off it: the same
`_run`/`runner.run` path, so it dies with the driver and is charged like every
other call, and codex reports no spend — which stays unknown, never $0.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from providers import codex, codex_text
from test_providers import fake

EXPECTED_TESTS = 5
DROP = ('{"decision": "drop", "why": "no source declares it", '
        '"gap": "nothing in the sources says what this card is for", "for_real": []}')


class TransportTest(unittest.TestCase):
    def test_the_review_door_calls_a_decision_malformed(self):
        """Why a neutral transport had to exist: the review door reads for a
        verdict, and a decision carries none."""
        out = codex(fake(f"echo '{DROP}'"), "decide this")
        self.assertEqual("malformed", out.kind)

    def test_the_transport_hands_back_what_the_model_said(self):
        out = codex_text(fake(f"echo '{DROP}'"), "decide this",
                         model="m", effort="max", cwd="", timeout=30)
        self.assertTrue(out.ok)
        self.assertEqual(DROP, out.text.strip())
        self.assertIsNone(out.verdict)

    def test_a_call_that_exited_badly_is_not_an_answer(self):
        """The exit code decides, never the text (a lesson about the harness)."""
        out = codex_text(fake(f"echo '{DROP}'; exit 3"), "decide this",
                         model="m", effort="max", cwd="", timeout=30)
        self.assertFalse(out.ok)

    def test_spend_codex_does_not_report_stays_unknown(self):
        """Unknown is not zero: a decider call this reads as free would make
        the campaign's spend a lie."""
        out = codex_text(fake(f"echo '{DROP}'"), "decide this",
                         model="m", effort="max", cwd="", timeout=30)
        self.assertIsNone(out.cost)
        self.assertIsNone(out.tokens)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
