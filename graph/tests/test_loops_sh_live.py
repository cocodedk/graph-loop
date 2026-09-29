"""graph/loops.sh with a person at the keys: Ctrl-C, and a key pressed while the command runs."""

import pathlib
import signal
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tmp_root  # noqa: F401
from loops_sh_rig import CLEAR, Rig


class Live(Rig):
    def test_ctrl_c_stops_with_the_message_and_status_0(self):
        proc = self.live("/proj")
        self.assertEqual([CLEAR + "\n", "SCREEN --screen /proj --refresh 30\n"],
                         [proc.stdout.readline(), proc.stdout.readline()])
        proc.send_signal(signal.SIGINT)
        rest, _ = proc.communicate(timeout=30)
        self.assertEqual((0, "\nstopped watching.\n"), (proc.returncode, rest))

    def test_a_key_pressed_while_the_command_runs_is_read_at_the_next_wait(self):
        proc = self.live("/proj", gate="1")
        self.wait_for("started")
        proc.stdin.write("f")
        proc.stdin.flush()
        (self.dir / "go").write_text("")
        out, _ = proc.communicate(timeout=30)
        self.assertEqual(0, proc.returncode)
        self.assertEqual(["-", "built"], self.filters())
        self.assertEqual("", (self.dir / "stdin").read_text())
        self.assertTrue(out.endswith("--only built --refresh 30\nstopped watching.\n"))


EXPECTED_TESTS = 2


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
