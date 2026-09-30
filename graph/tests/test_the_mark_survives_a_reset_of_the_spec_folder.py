"""A spec whose front matter lost its `lean_status` (a checkout, a stash, a branch switch) still shows the mark
the loop's own event log gives it: the newest event that names the spec decides (docs/lean/14-status-from-events.md)."""

import calendar
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import alert_email
import lean_run
import loops_list
import loops_projects
import project_specs
import review
import tmp_root  # noqa: F401
from project_specs import BUILDING, BUILT, PR_OPEN, QUESTION, STOPPED, WAITING
from providers import Outcome
from test_keep import repo
from test_project_marks import front, git, project, using
from workspace import Workspace

EXPECTED_TESTS = 10
SPEC = "01-x"
ASKED = {"kind": "lean_grilled", "specs": [SPEC], "questions": "Blue or red?"}
CLEAR = {"kind": "lean_grilled", "specs": [SPEC], "questions": ""}
STARTED = {"kind": "lean_feature_started", "task": SPEC}
STOP = {"kind": "lean_stopped", "task": SPEC}
PUBLISHED = {"kind": "lean_published", "task": SPEC}


def log(root, *rows, name="events.jsonl"):
    """The project's lean event log: `rows` (dicts or raw lines), one per line."""
    folder = pathlib.Path(root) / "scratchpad" / "lean"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("".join((row if isinstance(row, str) else json.dumps(row)) + "\n" for row in rows))


def marked(text, *rows, running=(), built=(), older=()):
    root = project(**{f"{SPEC}.md": text})
    if older:
        log(root, *older, name="events-0001.jsonl")
    if rows:
        log(root, *rows)
    return project_specs.mark(root / "docs" / "lean" / f"{SPEC}.md", set(running), set(built))


class Grilled(unittest.TestCase):
    def test_the_grill_event_names_the_specs_it_read_and_keeps_its_other_fields(self):
        ws = Workspace(tempfile.mkdtemp())
        (ws.root / "contact").write_text("person@example.test\n")
        folder = pathlib.Path(tempfile.mkdtemp())
        specs = [folder / "01-a.md", folder / "02 b.md"]
        for path in specs:
            path.write_text("Make it blue, and make it red.\n")
        with mock.patch.object(review, "codex", return_value=Outcome("ok", verdict="REJECT", text="Blue or red?")), \
                mock.patch.object(alert_email, "send", lambda *a, **k: None):
            lean_run.grill(ws, repo(), [str(path) for path in specs], "profile.md")
        row = next(row for row in ws.events() if row["kind"] == "lean_grilled")
        self.assertEqual(["01-a", "02-b"], row["specs"])
        self.assertEqual(("REJECT", "ok", "Blue or red?"), (row["verdict"], row["outcome"], row["questions"]))


class Log(unittest.TestCase):
    def test_a_grill_with_questions_a_stop_and_a_publish_give_their_marks(self):
        self.assertEqual(QUESTION, marked("Spec.\n", ASKED))
        self.assertEqual(STOPPED, marked("Spec.\n", ASKED, STARTED, STOP))
        self.assertEqual(PR_OPEN, marked("Spec.\n", ASKED, STARTED, PUBLISHED))

    def test_a_newer_start_or_a_newer_clear_grill_clears_it_and_an_older_event_never_decides(self):
        self.assertEqual(WAITING, marked("Spec.\n", ASKED, STARTED))
        self.assertEqual(WAITING, marked("Spec.\n", STOP, CLEAR))
        self.assertEqual(WAITING, marked("Spec.\n", PUBLISHED, STARTED))
        self.assertEqual(STOPPED, marked("Spec.\n", STARTED, ASKED, STARTED, STOP))
        self.assertEqual(QUESTION, marked("Spec.\n", STARTED, STOP, ASKED))

    def test_events_that_name_another_spec_or_say_nothing_about_a_status_change_nothing(self):
        other = {"kind": "lean_stopped", "task": "02-y"}
        noise = {"kind": "attempt", "task": SPEC, "purpose": "build"}
        self.assertEqual(QUESTION, marked("Spec.\n", ASKED, other, noise, {"kind": "lean_grilled", "specs": ["02-y"],
                                                                          "questions": ""}))
        self.assertEqual(STOPPED, marked("Spec.\n", STOP, noise, {"kind": "lean_grilled"}))

    def test_a_front_matter_status_wins_over_the_log_and_built_and_building_win_over_both(self):
        self.assertEqual(PR_OPEN, marked(front("pr_open"), ASKED))
        self.assertEqual(WAITING, marked(front("done"), ASKED))
        self.assertEqual(BUILT, marked(front("pr_open"), ASKED, built=[SPEC]))
        self.assertEqual(BUILT, marked("Spec.\n", ASKED, built=[SPEC]))
        self.assertEqual(BUILDING, marked("Spec.\n", STOP, running=[SPEC]))

    def test_a_spec_no_event_names_no_log_and_broken_lines_behave_as_before(self):
        self.assertEqual(WAITING, marked("Spec.\n", {"kind": "lean_stopped", "task": "02-y"}))
        self.assertEqual(WAITING, marked("Spec.\n"))
        self.assertEqual(QUESTION, marked("Spec.\n", "{broken", ASKED, "[1, 2]", "", '{"kind": "lean_stopped"'))
        self.assertEqual(WAITING, marked("Spec.\n", "not json at all"))

    def test_a_record_with_a_malformed_kind_or_specs_is_skipped(self):
        bent = [{"task": SPEC, "kind": []}, {"task": SPEC, "kind": {"a": 1}}, {"task": SPEC, "kind": None},
                {"kind": "lean_grilled", "specs": SPEC, "questions": "x"},
                {"kind": "lean_grilled", "specs": [[], {}], "questions": "x"}]
        self.assertEqual(WAITING, marked("Spec.\n", *bent))
        self.assertEqual(STOPPED, marked("Spec.\n", STOP, *bent))

    def test_the_rotated_parts_come_before_the_open_one(self):
        self.assertEqual(QUESTION, marked("Spec.\n", ASKED, older=[STARTED, STOP]))
        self.assertEqual(STOPPED, marked("Spec.\n", STOP, older=[ASKED]))

    def test_reading_the_log_writes_nothing(self):
        root = project(**{f"{SPEC}.md": "Spec.\n"})
        log(root, ASKED)
        files = sorted(str(path) for path in root.rglob("*") if path.is_file())
        before = [pathlib.Path(path).read_bytes() for path in files]
        project_specs.mark(root / "docs" / "lean" / f"{SPEC}.md", set(), set())
        self.assertEqual(files, sorted(str(path) for path in root.rglob("*") if path.is_file()))
        self.assertEqual(before, [pathlib.Path(path).read_bytes() for path in files])


class List(unittest.TestCase):
    def test_the_waiting_block_shows_a_spec_whose_front_matter_was_wiped(self):
        parent = pathlib.Path(tempfile.mkdtemp())
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(parent / "state")}):
            root = parent / "shop"
            (root / "docs" / "lean").mkdir(parents=True)
            (root / "docs" / "lean" / f"{SPEC}.md").write_text("Spec.\n")
            log(root, ASKED)
            file = loops_projects.path()
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(f"{root}\n")
            with using(git()):
                shown = loops_list.report("    PID ELAPSED COMMAND\n", lambda pid: None,
                                          calendar.timegm((2026, 9, 30, 9, 0, 0)), False)
        self.assertEqual("no lean loops running\n\nwaiting for you:\nshop  01-x  awaiting answer", shown)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
