"""A project's `rules.md` is settled for the grill and followed by the builder (issue #254).

Some specs went through four to seven grill rounds, most questions about states no page defines (loading, error,
empty). One shared rule every spec cited ended that: the specs that cited it were accepted in one or two rounds.
`rules.md` beside the specs is read with `lessons.md`, as a section of its own the grill must not ask about,
and it is never listed as a spec.
"""

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_body
import lean_budget
import lean_spec
import project_specs
import tmp_root  # noqa: F401

EXPECTED_TESTS = 4
RULES = "Every screen has a loading, an error and an empty state: a spinner, a retry line, a short invitation."


def folder(**files):
    root = pathlib.Path(tempfile.mkdtemp())
    (root / "docs" / "lean").mkdir(parents=True)
    for name, text in files.items():
        (root / "docs" / "lean" / name).write_text(text)
    return root


class Rules(unittest.TestCase):
    def test_a_rules_file_becomes_a_settled_section_of_the_grills_and_the_builders_prompts(self):
        notes = lean_spec.lessons(folder(**{"rules.md": RULES}) / "docs" / "lean")
        self.assertIn("## The project's standing rules (settled", notes)
        self.assertIn(RULES, notes)
        self.assertIn(notes, lean_body.grill_prompt("profile.md", notes, "spec"))
        self.assertIn(notes, lean_body.builder_prompt("spec", "gate.sh", "profile.md", notes, False))

    def test_no_notes_add_nothing_and_both_files_keep_both_sections(self):
        root = folder()
        self.assertEqual("", lean_spec.lessons(root / "docs" / "lean"))
        both = lean_spec.lessons(folder(**{"rules.md": RULES, "lessons.md": "Say which tests may change."}) / "docs" / "lean")
        self.assertIn("## Lessons from earlier runs of this project (hints to check, never proof)", both)
        self.assertIn("## The project's standing rules (settled", both)

    def test_a_rules_file_is_never_listed_as_a_spec(self):
        root = folder(**{"rules.md": RULES, "01-ring.md": "Show the ring."})
        self.assertEqual(["01-ring.md"], [path.name for path in project_specs.spec_files(str(root))])
        later = lean_budget.review_note(str(root / "docs" / "lean" / "00-first.md"))
        self.assertNotIn("rules", later)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())   # the three above and this one


if __name__ == "__main__":
    unittest.main()
