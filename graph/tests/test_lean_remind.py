"""When a project's lean loop is idle and a branch waits on the owner, a small command mails a reminder: at 30
minutes, 4 hours and 24 hours after it first sees the same set of branches, never two within an hour, then
silence. Time, processes, git and mail are all faked."""

import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import alert_email
import lean_remind
import lean_reminders
import tmp_root  # noqa: F401
from workspace import Workspace

EXPECTED_TESTS = 10
MIN, HOUR = 60, 3600
A, B = ["origin/lean/a"], ["origin/lean/a", "origin/feat/b"]
HEAD = "    PID ELAPSED COMMAND\n"


class Ladder(unittest.TestCase):
    def walk(self, moments, branches=A, running=False, state=None):
        """Run `step` at each (seconds, branches); a send is taken as accepted. The list of (when, action)."""
        state, log = state or {}, []
        for when, now_branches in moments:
            action, state = lean_reminders.step(state, now_branches or branches, running, when)
            if action == "send":
                state = lean_reminders.sent(state, when)
            log.append((when, action))
        return log, state

    def test_three_mails_at_thirty_minutes_four_hours_and_a_day_then_silence(self):
        moments = [(0, A), (29 * MIN, A), (30 * MIN, A), (31 * MIN, A), (4 * HOUR, A), (5 * HOUR, A),
                   (24 * HOUR, A), (48 * HOUR, A)]
        log, _ = self.walk(moments)
        self.assertEqual([(30 * MIN, "send"), (4 * HOUR, "send"), (24 * HOUR, "send")],
                         [(when, action) for when, action in log if action == "send"])

    def test_a_long_gap_sends_one_mail_and_never_a_burst(self):
        log, _ = self.walk([(0, A), (30 * HOUR, A), (30 * HOUR + MIN, A), (31 * HOUR + MIN, A)])
        self.assertEqual([(30 * HOUR, "send"), (31 * HOUR + MIN, "send")],
                         [(when, action) for when, action in log if action == "send"])

    def test_a_changed_set_starts_again_and_an_empty_one_clears(self):
        _, state = self.walk([(0, A), (30 * MIN, A), (4 * HOUR, A)])
        self.assertEqual(2, state["sent"])
        action, state = lean_reminders.step(state, B, False, 5 * HOUR)
        self.assertEqual((0, 5 * HOUR, "wait"), (state["sent"], state["since"], action))
        self.assertEqual(("clear", {}), lean_reminders.step(state, [], False, 6 * HOUR))

    def test_a_running_loop_is_left_quiet_and_its_state_kept(self):
        _, state = self.walk([(0, A)])
        self.assertEqual(("quiet", state), lean_reminders.step(state, A, True, 5 * HOUR))


class Reminder(unittest.TestCase):
    def setUp(self):
        self.folder = pathlib.Path(tempfile.mkdtemp())
        self.mails, self.accept = [], True

    def run_once(self, now, branches=A, ps=HEAD):
        def mail(subject, body):
            self.mails.append((subject, body))
            return self.accept
        return lean_reminders.remind("/work/proj", str(self.folder), now=now, ps_text=ps, cwd_for=lambda pid: "/work",
                                     unmerged=lambda repo: branches, mail=mail)

    def test_a_failed_send_does_not_advance_and_the_next_run_tries_again(self):
        self.run_once(0)
        self.accept = False
        self.run_once(31 * MIN)
        self.assertEqual(0, json.loads((self.folder / "remind.json").read_text())["sent"])
        self.accept = True
        self.run_once(32 * MIN)
        self.assertEqual(1, json.loads((self.folder / "remind.json").read_text())["sent"])
        self.assertEqual(2, len(self.mails))

    def test_the_mail_names_the_project_the_branches_and_which_reminder_it_is(self):
        self.run_once(0)
        self.run_once(4 * HOUR, branches=B)             # a changed set: the first sighting again
        self.run_once(4 * HOUR + 31 * MIN, branches=B)
        subject, body = self.mails[0]
        self.assertIn("proj", subject)
        for text in ("origin/lean/a", "origin/feat/b", "idle", "review and merge", "reminder 1 of 3"):
            self.assertIn(text, body)

    def test_a_loop_running_on_the_project_keeps_the_command_quiet(self):
        ps = HEAD + "9 100 python3 graph/lean.py --workspace /w --repo /work/proj --spec docs/lean/01-a.md\n"
        self.run_once(0, ps=ps)
        self.run_once(5 * HOUR, ps=ps)
        self.assertEqual([], self.mails)


class Entry(unittest.TestCase):
    def argv(self):
        folder = tempfile.mkdtemp()
        return ["--repo", "/work/proj", "--workspace", folder]

    def test_a_check_that_cannot_ask_git_says_so_sends_nothing_and_fails(self):
        def down(repo):
            raise RuntimeError("git fetch failed")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = lean_remind.main(self.argv(), read_ps=lambda: HEAD, unmerged=down, clock=lambda: 0)
        self.assertEqual(1, code)
        self.assertIn("nothing sent", out.getvalue())

    def test_a_check_prints_one_line_for_the_cron_log(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = lean_remind.main(self.argv(), read_ps=lambda: HEAD, unmerged=lambda repo: [], clock=lambda: 0)
        self.assertEqual((0, "proj: clear\n"), (code, out.getvalue()))


class Sent(unittest.TestCase):
    def test_mail_person_says_whether_it_sent(self):
        ws = Workspace(tempfile.mkdtemp())
        (ws.root / "contact").write_text("person@example.test\n")
        with mock.patch.object(alert_email, "send", return_value=None):
            self.assertTrue(ws.mail_person("subject", "body"))
        with mock.patch.object(alert_email, "send", side_effect=OSError("down")):
            self.assertFalse(ws.mail_person("subject", "body"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
