"""No card's gate writes where nobody removes it, and the rule has one author.

A gate that tees into `/tmp/<fixed name>` shares that one file with every
concurrent run of it, and a `$$` name leaves a fresh file behind on every
combined re-run — a kept card's gate re-runs on every later keep. /tmp filling
on 2026-09-03 killed every process on the host. The driver gives each gate a
home, points `$TMPDIR` at it and removes it when the gate ends.

An independent reviewer caught the first version of this file grepping the gate
text for `/tmp/` and `$$`, which is a second, worse copy of a rule the slicer
already owns — it passed `"$TMPDIR/../leak"`, which walks straight back out of
the home, and failed `test -d /tmp/cache`, which writes nothing. So the check
here IS `slicer/gate_output.py::unsafe_gate_sinks`, asked of every non-live
card. Nothing is lost by dropping the `$$` grep: a `$$` name inside `$TMPDIR`
goes with the home, and anywhere else it is already an unowned write.

A live gate is skipped: it is the commander's own text and runs unconfined
(`gates.run_gate(confine=False)`), so no TMPDIR is given to it.

The two checks that graded a whole backlog card by card stayed with the
repository that had one: they read `where.backlog()` and an excused list of
that repository's card names. What travels is the rule itself.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "slicer"))

from backlog_status import is_live
from gate_output import unsafe_gate_sinks  # type: ignore[import-not-found]

EXPECTED_TESTS = 2


def _leaks(task: dict) -> list[str]:
    """What this card's gate writes that nobody removes — the slicer's own
    rule, never a second reading of it."""
    return [] if is_live(task) else unsafe_gate_sinks(str(task.get("gate") or ""))


class GateScratchTest(unittest.TestCase):
    def test_a_write_that_walks_back_out_of_the_owned_home_is_refused(self):
        # `$TMPDIR` in the name proves nothing: `..` leaves the home again.
        self.assertTrue(_leaks({"gate": 'set -e -o pipefail\n(echo x > "$TMPDIR/../leak")'}))

    def test_reading_a_path_under_tmp_is_not_a_write(self):
        # The rule is about what a gate WRITES. A gate that only looks at a
        # path under /tmp leaves nothing behind and is nobody's leak.
        self.assertEqual([], _leaks({"gate": "set -e -o pipefail\n(test -d /tmp/cache)"}))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
