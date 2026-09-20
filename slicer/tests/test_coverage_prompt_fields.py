"""The coverage prompt reads no field the digest does not hash.

Twice now an accepted verdict has survived a backlog the reviewer would read
differently: `gate` and `done_when` were shown but not hashed, and then
`sliced_from` was read by `replacements` but not hashed. Both were the same rule
broken — the coverage prompt is a pure function of the source bytes and the
CONTRACT-projected rows, and `backlog_digest` hashes exactly that projection.

Restating that rule in commit messages did not hold it. This does: a field
taught to `index`, to `replacements` or to either filter has to be declared in
CONTRACT to be seen at all, because a row stripped to CONTRACT must produce the
same prompt as the whole row.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from asking import CONTRACT, coverage_prompt

EXPECTED_TESTS = 1

# How the work went, never what was promised: every such key the live tree
# carries. None of it may reach the reviewer.
RUN_STATE = {
    "worktree": "/tmp/drive-a/task-T18", "rebuild_from": "/tmp/drive-a/task-T18",
    "session": "01J", "session_account": "plan", "rebuild_round": 2, "rounds": 3,
    "replans": 1, "replan_history": ["rewritten once"], "rejections": 2,
    "refused_why": "the gate did not fail first", "kept_at": "2026-09-08T00:00:00Z",
    "commit": "deadbeef", "triage": "work", "blocked_by_human": True,
    "contract_seen": "a digest", "done_why": "the gate passed", "sliced_into": ["T18"],
    "gate_reviewed_first": True, "dependency_note": "T1 first", "subtasks_source": "T12",
    "finished": {"phase": "gate", "tree": "/tmp/drive-a/task-T18", "contract": "a digest",
                 "diff": "a digest"},
}

ROWS = [
    {"id": "T1", "status": "done", "goal": "the prerequisite", **RUN_STATE},
    {"id": "T12", "status": "sliced", "goal": "the replaced one", "needs": ["T1"],
     "source": ["specs/greeting.md:1"], **RUN_STATE},
    {"id": "T18", "status": "todo", "goal": "the replacement", "sliced_from": "T12",
     "files": ["app.py"], "gate": "set -e -o pipefail\nfalse",
     "done_when": "the greeting test passes", **RUN_STATE},
]


class FieldsTest(unittest.TestCase):
    def test_the_prompt_is_the_same_for_a_row_stripped_to_its_digested_fields(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        source = repo / "greeting.md"
        source.write_text("## Goal\nReturn a greeting.\n", "utf-8")
        stripped = [{key: value for key, value in row.items() if key in CONTRACT}
                    for row in ROWS]

        self.assertEqual(coverage_prompt(repo, [source], ROWS),
                         coverage_prompt(repo, [source], stripped))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
