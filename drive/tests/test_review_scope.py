"""Only a demonstrated defect in this change can send its builder back."""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from review_scope import read, validate

DIFF = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-one\n+two\n"
EXPECTED_TESTS = 11


def answer(findings=None, observations=None):
    findings = findings or []
    return json.dumps({"review": "REJECT" if findings else "ACCEPT",
                       "accept": not findings, "findings": findings,
                       "observations": observations or []})


def finding(**extra):
    return {"diff_line": 6, "requirement": "done_when", "problem": "Wrong value",
            "evidence": "The changed value fails the declared result", **extra}


class ScopeTest(unittest.TestCase):
    def test_an_unrelated_observation_does_not_block_acceptance(self):
        body = validate(answer(observations=["Old module could be smaller"]), DIFF)
        self.assertEqual("ACCEPT", body["review"])
        self.assertEqual(["Old module could be smaller"], body["observations"])

    def test_a_blocker_names_a_change_and_a_requirement(self):
        body = validate(answer([finding()], ["Separate cleanup"]), DIFF)
        self.assertEqual([finding()], body["findings"])
        self.assertEqual("REJECT", body["review"])

    def test_context_headers_and_absent_lines_cannot_anchor_a_blocker(self):
        for line in (0, 1, 2, 3, 4, 7, True):
            with self.subTest(line=line), self.assertRaises(ValueError):
                validate(answer([finding(diff_line=line)]), DIFF)

    def test_a_deletion_can_anchor_a_blocker(self):
        self.assertEqual("REJECT", validate(answer([finding(diff_line=5)]), DIFF)["review"])

    def test_empty_reject_and_accept_with_blockers_are_malformed(self):
        for text in (answer().replace('"ACCEPT"', '"REJECT"').replace('true', 'false'),
                     answer([finding()]).replace('"REJECT"', '"ACCEPT"').replace('false', 'true')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                read(text)

    def test_a_blocker_without_evidence_or_a_known_requirement_is_malformed(self):
        for extra in ({"evidence": " "}, {"requirement": "whole repository"},
                      {"problem": ""}, {"unexpected": "ignored"}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                read(answer([finding(**extra)]))

    def test_closed_shape_rejects_duplicate_keys_and_extra_answers(self):
        for text in (answer().replace('"accept": true', '"accept": true, "accept": true'),
                     answer() + "\nREVIEW: ACCEPT", answer().replace('"observations": []',
                     '"observations": [], "next_task": "fix everything"')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                read(text)

    def test_lists_are_small_and_observations_are_plain_nonempty_text(self):
        for text in (answer([finding()] * 4),
                     answer(observations=[{}]), answer(observations=[""])):
            with self.subTest(text=text), self.assertRaises(ValueError):
                read(text)

    def test_a_fourth_observation_is_dropped_rather_than_refused(self):
        """This used to raise with the other lists above, and refusing it threw
        away a whole paid build that nothing could retry out of — the same diff
        draws the same four observations every time. An observation blocks
        nothing and reaches no builder, so the extras go and the verdict stands;
        the findings cap above is a different thing and did not move."""
        self.assertEqual(["x"] * 3, read(answer(observations=["x"] * 4))["observations"])

    def test_git_metadata_changes_can_anchor_a_blocker(self):
        changes = (
            "old mode 100644\nnew mode 100755\n",
            "new file mode 100644\n", "deleted file mode 100644\n",
            "similarity index 100%\nrename from a.py\nrename to b.py\n",
            "similarity index 100%\ncopy from a.py\ncopy to b.py\n",
            "Binary files a/a.py and b/a.py differ\n", "GIT binary patch\nliteral 1\nA\n")
        for change in changes:
            diff = "diff --git a/a.py b/b.py\n" + change
            anchor = 3 if change.startswith("similarity") else 2
            with self.subTest(change=change):
                self.assertEqual("REJECT", validate(answer([finding(diff_line=anchor)]), diff)["review"])

    def test_metadata_headers_context_and_unframed_markers_are_not_changes(self):
        diffs = (
            ("new mode 100755\n", 1),
            ("diff --git a/a.py b/b.py\nindex 111..222 100644\n", 2),
            ("diff --git a/a.py b/b.py\nsimilarity index 100%\n", 2),
            (DIFF + " new mode 100755\n", 7),
            ("diff --git a/a.py b/b.py\nGIT binary patch\nliteral 1\nA\n", 3))
        for diff, anchor in diffs:
            with self.subTest(diff=diff), self.assertRaises(ValueError):
                validate(answer([finding(diff_line=anchor)]), diff)


class CountTest(unittest.TestCase):
    def test_count(self):
        suite = unittest.TestLoader().discover(str(pathlib.Path(__file__).parent),
                                              pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, suite.countTestCases())


if __name__ == "__main__":
    unittest.main()
