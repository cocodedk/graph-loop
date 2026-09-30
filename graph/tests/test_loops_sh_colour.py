"""graph/loops.sh passes `--color` on a terminal (faked with a pty) while NO_COLOR is unset or empty."""

import os
import pathlib
import pty
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tmp_root  # noqa: F401
from loops_sh_rig import GRAPH, Rig

EXPECTED_TESTS = 2


class Colour(Rig):
    def calls_of(self, *args, terminal, no_color=None):
        """What the fake command was asked when loops.sh ran with its output on a pty (`terminal`) or a pipe."""
        env = self.env("0.2")
        env.pop("NO_COLOR", None)
        if no_color is not None:
            env["NO_COLOR"] = no_color
        master, slave = pty.openpty()
        try:
            subprocess.run(["bash", str(GRAPH / "loops.sh"), *args], input="", env=env, cwd=self.here, timeout=60,
                           stdout=slave if terminal else subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        finally:
            os.close(master)
            os.close(slave)
        return self.calls()

    def test_a_terminal_with_no_color_unset_or_empty_gets_the_option_live_and_once(self):
        for no_color in (None, ""):
            with self.subTest(no_color=no_color):
                self.assertEqual(["--screen /proj --refresh 0.2 --color --once"],
                                 self.calls_of("-1", "/proj", terminal=True, no_color=no_color))
                self.assertEqual(["--screen /proj --refresh 0.2 --color"],
                                 self.calls_of("/proj", terminal=True, no_color=no_color))

    def test_no_terminal_or_a_set_no_color_gets_plain_text(self):
        for terminal, no_color in ((False, None), (False, ""), (True, "1"), (False, "1")):
            with self.subTest(terminal=terminal, no_color=no_color):
                self.assertEqual(["--screen /proj --refresh 0.2 --once"],
                                 self.calls_of("-1", "/proj", terminal=terminal, no_color=no_color))
                self.assertEqual(["--screen /proj --refresh 0.2"],
                                 self.calls_of("/proj", terminal=terminal, no_color=no_color))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
