"""A project's specs and their marks: which files count, which mark wins, and how built is read."""

import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import project_specs
import tmp_root  # noqa: F401
from project_specs import BUILDING, BUILT, PR_OPEN, STOPPED, WAITING


def project(**files):
    """A temporary project folder whose docs/lean holds `files` (name -> text or bytes)."""
    root = pathlib.Path(tempfile.mkdtemp())
    (root / "docs" / "lean").mkdir(parents=True)
    for name, body in files.items():
        path = root / "docs" / "lean" / name
        path.write_bytes(body if isinstance(body, bytes) else body.encode())
    return root


def git(subjects=(), refs=("origin/main", "main")):
    """A fake `subprocess.run` that knows `refs`; its calls are kept in `.calls`. Use it with `using`."""
    def run(command, **_):
        run.calls.append(command)
        if command[-1] in refs:
            return subprocess.CompletedProcess(command, 0, "".join(f"{s}\n" for s in subjects), "")
        return subprocess.CompletedProcess(command, 128, "", "fatal: bad revision")
    run.calls = []
    return run


def using(run):
    """Stand `run` in for the git call of project_specs."""
    return mock.patch.object(project_specs.subprocess, "run", run)


def front(status):
    return f"---\nlean_status: {status}\n---\nbody\n"


class Files(unittest.TestCase):
    def test_only_md_files_but_lessons_are_specs_by_file_name(self):
        root = project(**{"b.md": "", "a.md": "", "lessons.md": "", "c.txt": "", "d.md.bak": ""})
        (root / "docs" / "lean" / "sub.md").mkdir()
        self.assertEqual(["a.md", "b.md"], [p.name for p in project_specs.spec_files(str(root))])


class Marks(unittest.TestCase):
    def mark(self, text, running=(), built=()):
        path = project(**{"01-x.md": text}) / "docs" / "lean" / "01-x.md"
        return project_specs.mark(path, set(running), set(built))

    def test_the_five_marks(self):
        self.assertEqual(BUILDING, self.mark("", running=["01-x"]))
        self.assertEqual(BUILT, self.mark("", built=["01-x"]))
        self.assertEqual(STOPPED, self.mark(front("stopped")))
        self.assertEqual(PR_OPEN, self.mark(front("pr_open")))
        self.assertEqual(WAITING, self.mark(front("done")))
        self.assertEqual(WAITING, self.mark("no front matter"))

    def test_building_beats_built_and_built_beats_the_front_matter(self):
        self.assertEqual(BUILDING, self.mark(front("stopped"), running=["01-x"], built=["01-x"]))
        self.assertEqual(BUILT, self.mark(front("pr_open"), built=["01-x"]))
        self.assertEqual(BUILT, self.mark(front("stopped"), built=["01-x"]))
        self.assertEqual(STOPPED, self.mark(front("stopped"), built=["01-y"]))

    def test_no_git_history_marks_nothing_built(self):
        path = project(**{"a.md": front("pr_open")}) / "docs" / "lean" / "a.md"
        self.assertEqual(PR_OPEN, project_specs.mark(path, set(), None))

    def test_a_name_with_spaces_or_punctuation_is_its_slug(self):
        path = project(**{"01 a (b).md": ""}) / "docs" / "lean" / "01 a (b).md"
        self.assertEqual(BUILDING, project_specs.mark(path, {"01-a-b"}, None))
        self.assertEqual(BUILT, project_specs.mark(path, set(), {"01-a-b"}))

    def test_a_file_that_cannot_be_read_or_parsed_has_no_front_matter(self):
        root = project(**{"bad.md": "---\nlean_status: [oops\n---\n", "latin.md": b"---\nx: \xe9\n---\n"})
        for name in ("bad.md", "latin.md", "gone.md"):
            with self.subTest(name=name):
                self.assertEqual(WAITING, project_specs.mark(root / "docs" / "lean" / name, set(), set()))

    def test_front_matter_that_is_not_a_mapping_has_no_status(self):
        path = project(**{"list.md": "---\n- stopped\n---\n"}) / "docs" / "lean" / "list.md"
        self.assertEqual(WAITING, project_specs.mark(path, set(), set()))


class Built(unittest.TestCase):
    def test_one_git_call_reads_origin_main(self):
        run = git(["feat(a): x", "fix: y", "feat(b)!: z"])
        with using(run):
            self.assertEqual({"a", "b"}, project_specs.built_names("/p"))
        self.assertEqual([["git", "-C", "/p", "log", "--format=%s", "origin/main"]], run.calls)

    def test_main_is_read_when_there_is_no_origin_main(self):
        run = git(["feat(a): x"], refs=("main",))
        with using(run):
            self.assertEqual({"a"}, project_specs.built_names("/p"))
        self.assertEqual(["origin/main", "main"], [call[-1] for call in run.calls])

    def test_with_neither_ref_nothing_is_built(self):
        with using(git(refs=())):
            self.assertIsNone(project_specs.built_names("/p"))

    def test_git_that_cannot_run_is_unreadable(self):
        def missing(*_, **__):
            raise FileNotFoundError("git")
        with using(missing):
            self.assertIsNone(project_specs.built_names("/p"))

    def test_a_subject_that_only_contains_the_feat_later_does_not_count(self):
        run = git(["fix: undo feat(a)", "docs: feat(b) notes", "Revert feat(c)", "feat: (d)"])
        with using(run):
            self.assertEqual(set(), project_specs.built_names("/p"))


EXPECTED_TESTS = 12


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
