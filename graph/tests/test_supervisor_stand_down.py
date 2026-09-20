"""supervisor.sh run for real with a stubbed driver: a quick rc 0 means the
backlog is worked out — logged as finished, standing down, never a counted
failure (C5) — and a driver that keeps dying under 30 s, rc 75 included, is
started five times with four backoffs and then left for a person (B6). Under
the old script, quick rc 0 was restarted four times and misreported as five
immediate failures.

That last stand-down kills the alarm ticker with it, and the ticker's first
check is 15 minutes away: before this, five immediate failures ended the loop
in silence. It now hands the stand-down to alert-watcher.sh, in front of its
own last log line, and exits non-zero (astra's review, finding 14)."""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

GRAPH = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GRAPH / "lib"))
import notice  # after the path line above, which is what makes it importable

EXPECTED_TESTS = 7


def run_supervisor(case: unittest.TestCase, run_exit: int,
                   camp: pathlib.Path | None = None,
                   email_ok_after: int = 0,
                   sleep_hook: str = "",
                   disk_full: bool = False,
                   plan_exit: int = 0) -> tuple[str, int, pathlib.Path]:
    """Run the real supervisor.sh against a stub driver exiting `run_exit` at
    once, with sleep a no-op so the backoffs collapse; returns the log, the
    exit code and the campaign directory. `camp` reuses an earlier run's
    campaign, which is how a second start meets what the first left behind, and
    each run starts with the stop flag and the stub counters cleared, as a
    person restarting the loop does.

    `email_ok_after` is the attempt on which the mail finally goes out; 0 means
    never, which is how a stand-down nobody can be told about is made. An
    undelivered stand-down leaves the supervisor retrying it and starting no
    driver, so the messenger stub plants the stop flag on its SECOND call: that
    is how a test ends notice-only mode, which otherwise ends only when a
    delivery is proved. `sleep_hook` is bash the sleep stub runs before it
    returns, for what another process does while the supervisor waits.

    `plan_exit` is what the plan phase exits with; it is stubbed like the
    driver, because the real one calls the slicer.

    `disk_full` is the answer the disk probe (`lib/view_pulse.py`) gives: it is
    stubbed either way, never left to the host's real free space, or every test
    here would depend on the disk of the machine that filled once.
    """
    if camp is None:
        camp = pathlib.Path(tempfile.mkdtemp())
        case.addCleanup(shutil.rmtree, camp, ignore_errors=True)
    for per_run in ("stop.flag", "messenger.count", "mail.count"):
        (camp / per_run).unlink(missing_ok=True)
    stub = camp / "bin"
    stub.mkdir(exist_ok=True)
    real = shutil.which("python3")
    (stub / "python3").write_text(
        "#!/bin/bash\n"
        'case "$*" in\n'
        f'  *"graph-goal.py run"*) exit {run_exit} ;;\n'
        f'  *"graph-goal.py plan"*) exit {plan_exit} ;;\n'
        '  *"graph-goal.py report"*) echo report ;;\n'
        # the disk probe answers in the board's own words, or says nothing at all
        + ('  *view_pulse.py*) echo "  DISK NEARLY FULL — 3.1 GB free where the worktrees live"'
           " ;;\n" if disk_full else "  *view_pulse.py*) exit 1 ;;\n") +
        f'  *alert_email.py*) n=$(_count {camp}/mail.count);'
        f' [ "$n" -ge {email_ok_after or 10**6} ] && exit 0; exit 1 ;;\n'
        f'  *) exec "{real}" "$@" ;;\n'
        "esac\n")
    (stub / "python3").chmod(0o755)
    # Every agent this can reach is faked: the stand-down calls the real
    # alert-watcher.sh, whose messenger would otherwise be a live claude call
    # and whose last resort would be a real email to the owner.
    (stub / "claude").write_text(
        f"#!/bin/bash\ncat > {camp}/prompt.txt\n"
        f'[ "$(_count {camp}/messenger.count)" -ge 2 ] && touch {camp}/stop.flag\nexit 1\n')
    (stub / "claude").chmod(0o755)
    # one counter reader for both stubs, on the PATH they already share
    (stub / "_count").write_text(
        '#!/bin/bash\nn=$(cat "$1" 2>/dev/null || echo 0); echo $((n + 1)) | tee "$1"\n')
    (stub / "_count").chmod(0o755)
    # Backoff sleeps collapse so the loop is testable; the 15-minute ticker's
    # sleep stays real, or its loop would spin hot and run real checks here.
    (stub / "sleep").write_text(
        '#!/bin/bash\n[ "$1" = "900" ] && exec /usr/bin/sleep 900\n' + sleep_hook + "exit 0\n")
    (stub / "sleep").chmod(0o755)
    env = dict(os.environ, PATH=f"{stub}:{os.environ['PATH']}",
               GRAPH_CAMPAIGN=str(camp))
    done = subprocess.run(["bash", str(GRAPH / "supervisor.sh")], env=env, check=False,
                          capture_output=True, text=True, timeout=60)
    return (camp / "supervisor.log").read_text("utf-8"), done.returncode, camp


class StandDownTest(unittest.TestCase):
    def test_one_quick_rc0_logs_completion_and_stands_down(self):
        log, code, _ = run_supervisor(self, run_exit=0)
        self.assertEqual(0, code)                                 # finished work is not a failure
        self.assertEqual(1, log.count("starting the driver"))     # one run, no restart
        self.assertIn("driver finished (rc=0)", log)
        self.assertIn("standing down", log.strip().splitlines()[-1])
        self.assertNotIn("five immediate failures", log)

    def test_a_driver_dying_at_once_on_rc75_is_left_for_a_person_after_five(self):
        log, _, _ = run_supervisor(self, run_exit=75)
        self.assertEqual(5, log.count("starting the driver"))     # backoff, then stop
        self.assertIn("five immediate failures: standing down for a person",
                      log.strip().splitlines()[-1])


class FatalAlertTest(unittest.TestCase):
    def test_the_five_failure_stand_down_alerts_before_it_exits_non_zero(self):
        log, code, camp = run_supervisor(self, run_exit=75)
        prompt = camp / "prompt.txt"
        self.assertTrue(prompt.exists(), "the messenger was never called")
        self.assertIn("the supervisor stood down", prompt.read_text("utf-8"))
        self.assertLess(log.index("alert-watcher"),                  # alerted first,
                        log.rindex("standing down for a person"))     # then stood down
        self.assertEqual(1, code)


class UndeliveredFatalTest(unittest.TestCase):
    """A stand-down nobody could be told about must outlive the process that
    tried: the ticker died with the supervisor, so alert-watcher.sh's "retrying
    next tick" promised a tick that no longer existed (astra's round-2 finding
    13). The notice stays on disk, the board carries it, and the next start
    tries again."""

    def test_a_stand_down_nobody_was_told_about_stays_on_the_board(self):
        log, _, camp = run_supervisor(self, run_exit=75)
        self.assertIn("nobody was reached", log)          # messenger and email both failed
        check = subprocess.run(["bash", str(GRAPH / "watch.sh"), "--check"], check=False,
                               env=dict(os.environ, GRAPH_CAMPAIGN=str(camp)),
                               capture_output=True, text=True, timeout=120)
        self.assertIn("the supervisor stood down", check.stdout)
        self.assertEqual(1, check.returncode)

    def test_the_next_start_sends_it_again(self):
        _, _, camp = run_supervisor(self, run_exit=75)
        (camp / "prompt.txt").unlink()                     # the attempt that failed
        run_supervisor(self, run_exit=0, camp=camp)        # a person restarts the loop
        self.assertIn("the supervisor stood down", (camp / "prompt.txt").read_text("utf-8"))


class TwoStandDownsTest(unittest.TestCase):
    """Two stand-downs are two notices, however alike their words.

    Codex on the finding-13 brick: the notice is compared with the payload just
    delivered, so two runs whose notices differ only in when they wrote them
    were the same notice — delivering the board of the older one took away the
    newer one, unread, under the lock. Both notices here are written by the
    real supervisor, and the payload is the real board's."""

    def test_delivering_the_older_notice_leaves_the_newer_one_standing(self):
        _, _, camp = run_supervisor(self, run_exit=75)
        older = (camp / "stand-down.txt").read_text("utf-8")
        board = subprocess.run(["bash", str(GRAPH / "watch.sh"), "--check"], check=False,
                               env=dict(os.environ, GRAPH_CAMPAIGN=str(camp)),
                               capture_output=True, text=True, timeout=120).stdout
        run_supervisor(self, run_exit=75, camp=camp)       # a second run, a second stand-down
        newer = (camp / "stand-down.txt").read_text("utf-8")
        self.assertNotEqual(older, newer)                  # each says which run wrote it
        self.assertFalse(notice.clear(camp, board), "the older board took the newer notice")
        self.assertTrue((camp / "stand-down.txt").exists())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
