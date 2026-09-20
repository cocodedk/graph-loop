"""A handoff kills only the session it started, and only one runs at a time.

Two ticks that both found the stand-in missing both launched one, and the
loser's cleanup killed the winner's live session (astra's round-3 finding 17).
Two guards, both here: the campaign's own `handoff.lock` means a second launch
never runs beside the first, and the cleanup kills a session only while the
identity file still names THIS run's id.

The fake tmux comes from test_handoff_two_campaigns.py, the front door of this
rig: one state file per session name, holding the command it was started with.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import pathlib
import shutil
import signal
import subprocess
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_handoff_two_campaigns import FAKE

GRAPH = pathlib.Path(__file__).resolve().parents[1]

EXPECTED_TESTS = 4
WINNER = "11111111-2222-3333-4444-555555555555"


def _kill(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)


class HandoffRig(unittest.TestCase):
    def setUp(self):
        self.state = pathlib.Path(tempfile.mkdtemp())
        self.stub = pathlib.Path(tempfile.mkdtemp())
        self.camp = pathlib.Path(tempfile.mkdtemp())
        for temp in (self.state, self.stub, self.camp):
            self.addCleanup(shutil.rmtree, temp, ignore_errors=True)
        # the script's own naming: md5 of the campaign path, first 8 hex
        self.session = "watcher-standin-" + hashlib.md5(
            str(self.camp).encode()).hexdigest()[:8]

    def tmux(self, script: str) -> None:
        fake = self.stub / "tmux"
        fake.write_text(script)
        fake.chmod(0o755)

    def handoff(self, **extra: str) -> subprocess.CompletedProcess:
        """A campaign with no init event of its own is pointed at a branch the
        only other way there is, in the environment (where.py); `extra`
        overrides it, for a case about another branch or about none at all."""
        env = dict(os.environ, GRAPH_CAMPAIGN=str(self.camp),
                   PATH=f"{self.stub}:{os.environ['PATH']}",
                   FAKE_TMUX_STATE=str(self.state), GRAPH_BRANCH="campaign/test")
        env.update(extra)
        return subprocess.run(["bash", str(GRAPH / "handoff-standin.sh")], env=env,
                              check=False, capture_output=True, text=True, timeout=60)


class OwnershipTest(HandoffRig):
    """The brief step fails, and by then another launch has taken the identity
    and the session over. The failing run must leave both alone."""

    def test_a_failing_launch_leaves_the_session_another_launch_took_over(self):
        # the stub plays the winner at load-buffer time, then fails the paste
        self.tmux(FAKE.replace(
            "  load-buffer|paste-buffer|send-keys) : ;;\n",
            f'  load-buffer)  printf "%s" "--session-id {WINNER}" '
            f'> "$FAKE_TMUX_STATE/{self.session}"; '
            f'printf "%s" "{WINNER}" > "{self.camp}/WATCHER-STANDIN.session" ;;\n'
            "  paste-buffer) exit 1 ;;\n"
            "  send-keys)    : ;;\n"))
        done = self.handoff()
        self.assertEqual(1, done.returncode, done.stdout)
        self.assertIn("pasting the standing brief failed", done.stdout)
        running = self.state / self.session
        self.assertTrue(running.exists(), "the loser killed the winner's session")
        self.assertIn(WINNER, running.read_text("utf-8"))
        self.assertEqual(WINNER, (self.camp / "WATCHER-STANDIN.session").read_text("utf-8"))


class OneAtATimeTest(HandoffRig):
    def test_a_second_handoff_starts_nothing_while_one_is_running(self):
        self.tmux(FAKE)
        held = subprocess.Popen(["flock", str(self.camp / "handoff.lock"),
                                 "-c", "sleep 5"])
        self.addCleanup(held.wait)
        self.addCleanup(held.kill)
        done = self.handoff()
        self.assertEqual(1, done.returncode)
        self.assertIn("another handoff for this campaign is running", done.stdout)
        self.assertEqual([], list(self.state.iterdir()))


class LockNotInheritedTest(HandoffRig):
    """The stand-in outlives this script, so it must not inherit the lock.

    A tmux client with no server forks one, and that server keeps every open
    descriptor for as long as the session lives — the lock would then be held
    by the stand-in itself, and every later handoff would say "another handoff
    is running" for ever. The same for `screen -dmS`.
    """

    def alive_session(self) -> str:
        """A fake tmux whose new-session leaves a process behind, as a real
        detached session does: it keeps whatever descriptors it was started
        with, and its stdio is its own or `handoff()` would wait for it."""
        return FAKE.replace(
            '  new-session)  printf \'%s\' "${@: -1}" > "$C" ;;\n',
            '  new-session)  printf \'%s\' "${@: -1}" > "$C"; '
            'setsid sleep 30 </dev/null >/dev/null 2>&1 & '
            'echo $! > "$FAKE_TMUX_STATE/pid"; ls /proc/self/fd > "$FAKE_TMUX_STATE/fds" ;;\n')

    def test_the_lock_is_free_again_while_the_started_session_lives(self):
        self.tmux(self.alive_session())
        self.assertIn("started", self.handoff().stdout)
        session = int((self.state / "pid").read_text("utf-8"))
        self.addCleanup(_kill, session)
        self.assertTrue(pathlib.Path("/proc", str(session)).exists(),
                        "the fake session did not stay alive")
        free = subprocess.run(["flock", "-n", str(self.camp / "handoff.lock"), "-c", "true"],
                              check=False, capture_output=True)
        self.assertEqual(0, free.returncode,
                         "the started session still holds the handoff lock")
        self.assertNotIn("7", (self.state / "fds").read_text("utf-8").split())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
