"""A diff over the reviewer's input limit is shortened, not refused (issue 224): a stat line for every file,
the whole sections of the smallest files that fit, and a list of the rest. The reviewer is faked."""

import pathlib
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_judge
import lean_shorten
import tmp_root  # noqa: F401
from providers import Outcome
from review_scope import VERDICT

EXPECTED_TESTS = 10
ACCEPT = Outcome("ok", verdict="ACCEPT", text="")
LIMIT = lean_judge.PROMPT_LIMIT


def section(name: str, lines: int, width: int = 50, removed: int = 0) -> str:
    return (f"diff --git a/{name} b/{name}\nindex 1..2 100644\n--- a/{name}\n+++ b/{name}\n"
            f"@@ -1,{removed} +1,{lines} @@\n" + ("+" + "x" * width + "\n") * lines + ("-gone\n") * removed)


def sized(name: str, characters: int) -> str:
    return section(name, characters // 51)


def asked(spec: str, diff: str, threads: str = "") -> tuple[str, mock.Mock]:
    with mock.patch.object(lean_judge.review, "codex", return_value=ACCEPT) as call, \
            mock.patch.object(lean_judge.lean_calls, "started", return_value={"effort": "medium"}):
        lean_judge.judge(mock.Mock(), "rest-ring", spec, diff, "/nowhere", threads=threads)
    return call.call_args.args[1], call


class Fits(unittest.TestCase):
    def test_a_first_builds_prompt_that_fits_carries_the_diff_whole(self):
        diff = sized("a.txt", 400000) + sized("b.txt", 400000)
        prompt = asked("the spec", diff)[0]
        self.assertTrue(len(prompt) <= LIMIT)
        self.assertIn(f"## Spec\n\nthe spec\n\n## The diff against main\n\n{diff}\n\n{VERDICT}", prompt)
        self.assertNotIn("Changed files", prompt)

    def test_a_revise_rounds_prompt_that_fits_carries_the_diff_whole(self):
        diff = sized("a.txt", 400000) + sized("b.txt", 400000)
        prompt = asked("the spec", diff, threads="fix it")[0]
        self.assertIn(f"## The diff this round made\n\n{diff}\n\n## The review threads this round answers\n\n"
                      f"fix it\n\n", prompt)
        self.assertNotIn("Changed files", prompt)


class Large(unittest.TestCase):
    def setUp(self):
        self.parts = {"a.txt": section("a.txt", 10), "b.txt": sized("b.txt", 300000),
                      "c.txt": sized("c.txt", 500000), "d.txt": sized("d.txt", 600000)}
        self.prompt = asked("the spec", "".join(self.parts.values()))[0]

    def test_the_prompt_fits_with_a_stat_for_every_file_and_a_list_of_what_is_left_out(self):
        self.assertTrue(len(self.prompt) <= LIMIT)
        self.assertIn("## Spec\n\nthe spec\n\n", self.prompt)
        for name in self.parts:
            self.assertRegex(self.prompt, rf"(?m)^{name} \| \+\d+ -0$")
        (_shown, rest) = self.prompt.split("## Not shown\n\n")
        self.assertIn(f"d.txt ({len(self.parts['d.txt'])} characters)\n", rest)
        self.assertNotIn("c.txt (", rest)
        self.assertIn("too large to include", rest)
        self.assertIn("worktree", rest)

    def test_a_shown_section_is_whole_and_a_left_out_one_is_absent(self):
        for name in ("a.txt", "b.txt", "c.txt"):
            self.assertIn(self.parts[name], self.prompt)
        self.assertNotIn(self.parts["d.txt"][:2000], self.prompt)
        self.assertLess(self.prompt.index(self.parts["a.txt"]), self.prompt.index(self.parts["b.txt"]))

    def test_a_file_bigger_than_the_budget_alone_is_listed_and_the_others_that_fit_are_shown(self):
        parts = [sized("big.txt", 1000000), section("a.txt", 10), sized("b.txt", 200000)]
        prompt = asked("the spec", "".join(parts))[0]
        self.assertTrue(len(prompt) <= LIMIT)
        self.assertIn(parts[1], prompt)
        self.assertIn(parts[2], prompt)
        self.assertNotIn(parts[0][:2000], prompt)
        self.assertIn(f"big.txt ({len(parts[0])} characters)\n", prompt)

    def test_the_stat_counts_are_the_diffs_and_a_dashed_line_is_not_a_header(self):
        tricky = section("a.txt", 3, removed=2).replace("-gone\n", "--- a comment\n", 1)
        self.assertEqual((3, 2), lean_shorten.counts(tricky))
        self.assertIn("a.txt | +10 -0\n", self.prompt)
        self.assertEqual("a.txt | +3 -2\n", lean_shorten._stat(("a.txt", tricky)))


class Squeezed(unittest.TestCase):
    def test_a_stat_and_a_list_that_do_not_fit_become_one_line_each(self):
        spec = "s" * 895000
        diff = "".join(section(f"f{n:03}.py", n, width=1) for n in range(1, 301))
        prompt = asked(spec, diff, threads="fix it")[0]
        kept = len(re.findall(r"(?m)^f\d+\.py \| \+\d+ -0$", prompt))
        self.assertTrue(len(prompt) <= LIMIT)
        self.assertTrue(0 < kept < 300)
        self.assertIn(f"... and {300 - kept} more files\n", prompt)
        self.assertIn("300 files not shown\n", prompt)
        self.assertIn("f300.py | +300 -0\n", prompt)
        self.assertNotIn("f001.py |", prompt)
        self.assertIn(spec, prompt)
        self.assertIn("fix it", prompt)

    def test_the_stat_is_shortened_before_the_list_of_files_not_shown_is(self):
        diff = "".join(section(f"f{n:03}.py", n, width=1) for n in range(1, 301))
        spec = "s" * (LIMIT - 12000 - len(asked("", "")[0]))
        prompt = asked(spec, diff)[0]
        self.assertTrue(len(prompt) <= LIMIT)
        self.assertRegex(prompt, r"\.\.\. and \d+ more files\n")
        self.assertNotIn("files not shown", prompt)
        self.assertEqual(300, len(re.findall(r"(?m)^f\d+\.py \(\d+ characters\)$", prompt)))

    def test_a_name_is_read_from_a_quoted_header_a_path_with_b_in_it_and_a_rename(self):
        quoted = 'diff --git "a/caf\\303\\251.txt" "b/caf\\303\\251.txt"\n--- a/x\n+++ b/x\n'
        spaced = "diff --git a/my b/notes.py b/my b/notes.py\n--- a/my b/notes.py\n+++ b/my b/notes.py\n"
        renamed = "diff --git a/old.py b/new b/x.py\nsimilarity index 90%\nrename from old.py\nrename to new b/x.py\n"
        self.assertEqual(["caf\\303\\251.txt", "my b/notes.py", "new b/x.py"],
                         [name for (name, _) in lean_shorten.sections(quoted + spaced + renamed)])

    def test_never_cut_parts_over_the_limit_are_sent_as_they_are(self):
        spec = "s" * 950000
        (prompt, call) = asked(spec, section("a.txt", 5) + section("b.txt", 5))
        self.assertEqual(1, call.call_count)
        self.assertIn(spec, prompt)
        self.assertIn("... and 2 more files\n", prompt)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
