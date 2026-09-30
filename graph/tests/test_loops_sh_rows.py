"""graph/loops.sh passes the terminal's height (`tput lines`, faked) to the command on every live refresh."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tmp_root  # noqa: F401
from loops_sh_rig import CLEAR, Rig


class Rows(Rig):
    def test_every_live_refresh_reads_and_passes_the_height_again(self):
        self.sh("/proj", keys="xx", rows="30 41 25")
        self.assertEqual([f"--screen /proj --refresh 0.2 --rows {height}" for height in (30, 41, 25)],
                         self.calls())

    def test_tput_that_prints_an_error_leaves_no_line_on_the_screen(self):
        (self.dir / "tput").write_text("#!/bin/sh\necho 'tput: No value for $TERM' >&2\nexit 3\n")
        done = self.sh("/proj", rows="37")
        self.assertEqual(f"{CLEAR}\nSCREEN --screen /proj --refresh 0.2\nstopped watching.\n", done.stdout)
        self.assertNotIn("TERM", done.stderr)

    def test_nothing_is_passed_when_tput_gives_nothing_or_no_number(self):
        for rows in ("", "tall"):
            with self.subTest(rows=rows):
                self.sh("/proj", keys="x", rows=rows)
                self.assertEqual(["--screen /proj --refresh 0.2"] * 2, self.calls())

    def test_one_look_never_passes_it(self):
        done = self.sh("-1", "/proj", rows="37")
        self.assertEqual("SCREEN --screen /proj --refresh 0.2 --once\n", done.stdout)
        self.assertEqual(["--screen /proj --refresh 0.2 --once"], self.calls())

    def test_a_key_that_reads_the_path_does_not_pass_it(self):
        self.path(1, "/fresh")
        self.sh("/proj", keys="1", rows="37")
        self.assertEqual(["--screen /proj --refresh 0.2 --rows 37", "--path 1",
                          "--screen /fresh --refresh 0.2 --rows 37"], self.calls())


EXPECTED_TESTS = 5


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
