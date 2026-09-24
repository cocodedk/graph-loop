"""Nothing in a log may stop the export — not one strange event, not any.

Three reviews found three different fields that took the whole run down: a
`task` that was a list, then a `name` that was a dict, then a refusal whose
`step` was a list. Each was fixed where it was found, and the next review
found the next one. So the guard moved: turning one event into a section, or
into an index entry, happens inside one try for that event, and whatever it
raises costs that event and nothing else.

This proves the class rather than the instance. Every kind the memory projects,
every field of it, replaced in turn by None, a list, a dict, a number and by
nothing at all: the export never raises, and every event is either counted or
has made a section — never neither, never both.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import remember
import remember_events
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 4

KINDS = [
    {"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
     "added": ["T30", "T30.schema"]},
    {"at": "2026-09-20T07:04:11Z", "kind": "attempt", "task": "T30.schema",
     "account": "work", "outcome": "ok", "counted": True, "cost": 0.4211,
     "tokens": 2912, "failed_gate": False, "purpose": "review", "unstarted": False},
    {"at": "2026-09-20T07:01:06Z", "kind": "refused", "task": "T30.schema",
     "step": "contract", "why": "a reason"},
    {"at": "2026-09-20T07:40:00Z", "kind": "rejected", "task": "T30.schema",
     "why": "a reason"},
    {"at": "2026-09-20T07:05:30Z", "kind": "step", "task": "T30.schema",
     "step": "gate", "seconds": 42.7, "passed": False, "code": 1},
    {"at": "2026-09-20T07:20:00Z", "kind": "accepted", "task": "T30.schema",
     "worktree": "/a/checkout", "commit": "9f1c2ab3"},
    {"at": "2026-09-20T07:05:31Z", "kind": "artifact", "task": "T30.schema",
     "name": "gate-output", "path": "/a/campaign/calls/T30.schema/001-gate-output.txt",
     "bytes": 4004},
]

INSTEAD = (None, ["a", "list"], {"a": "dict"}, 41, 0.5, True, "")


def mutations() -> list[dict]:
    """Every kind, with every field in turn replaced by something else — and
    once with that field taken out altogether."""
    rows = []
    for row in KINDS:
        for field in row:
            for value in INSTEAD:
                rows.append({**row, field: value})
            rows.append({key: held for key, held in row.items() if key != field})
    return rows


def vault() -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp()) / "vault"
    piece = root / "T30"
    piece.mkdir(parents=True)
    (piece / cardfile.HEAD).write_text(
        cardfile.dump({"goal": "a piece", "status": "sliced"}), "utf-8")
    (piece / "01-schema.md").write_text(
        cardfile.dump({"goal": "the field exists", "status": "todo"}), "utf-8")
    return root


class EveryFieldOfEveryKindBentInTurn(unittest.TestCase):
    def test_the_fuzz_is_as_wide_as_it_claims(self):
        self.assertEqual(sum((len(INSTEAD) + 1) * len(row) for row in KINDS),
                         len(mutations()))
        self.assertGreater(len(mutations()), 300)

    def test_not_one_of_them_raises_and_each_is_counted_exactly_once(self):
        for row in mutations():
            with self.subTest(kind=row.get("kind"), row=sorted(row)):
                memory, counts = remember_events.dated([row])
                self.assertEqual(
                    1, counts["unreadable"] + counts["no_section"] + bool(memory),
                    "an event is counted, or it made a section, never both or neither")

    def test_the_whole_bent_log_still_exports(self):
        root = vault()
        counts = remember.write_memory(root, mutations())
        self.assertEqual(len(mutations()), counts["events"])
        self.assertEqual(2, counts["written"] + counts["unchanged"])


class ARefusalWhoseStepIsNotAString(unittest.TestCase):
    def test_it_is_counted_and_the_rest_of_the_log_still_lands(self):
        """The instance the third review found, kept as its own case: it is
        the one that showed a field check per field was never going to hold."""
        root = vault()
        counts = remember.write_memory(root, [
            {"at": "2026-09-20T07:01:06Z", "kind": "refused", "task": "T30.schema",
             "step": ["contract"], "why": "a reason"},
            {"at": "2026-09-20T07:05:30Z", "kind": "step", "task": "T30.schema",
             "step": "gate", "seconds": 8.25, "passed": True, "code": 0},
        ])
        self.assertEqual(1, counts["unreadable"])
        self.assertIn("the gate ran, exit 0",
                      (root / "T30" / "relatives" / "memory-01-schema.md").read_text("utf-8"))


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
