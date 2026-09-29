"""graph/loops.sh: the keys, the refresh and the edges, with the command it calls faked."""

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tmp_root  # noqa: F401
from loops_sh_rig import CLEAR, FAILED, GRAPH, Rig


class Script(Rig):
    def test_one_look_passes_the_folder_and_no_filter_and_does_not_clear(self):
        done = self.sh("-1", "/proj", keys="f")
        self.assertEqual((0, "SCREEN --screen /proj --refresh 0.2 --once\n"), (done.returncode, done.stdout))
        self.assertEqual("SCREEN --screen --refresh 0.2 --once\n", self.sh("-1").stdout)

    def test_live_it_clears_before_each_print_and_passes_the_refresh(self):
        done = self.sh("/proj", refresh="7")
        self.assertEqual((0, f"{CLEAR}\nSCREEN --screen /proj --refresh 7\nstopped watching.\n"),
                         (done.returncode, done.stdout))
        self.assertEqual(f"{CLEAR}\nSCREEN --screen --refresh 15\nstopped watching.\n",
                         self.sh(refresh="").stdout)

    def test_a_digit_switches_the_folder_and_the_screen_printed_next_shows_it(self):
        self.path(2, "/other")
        done = self.sh("/proj", keys="2")
        self.assertEqual([["SCREEN --screen /proj --refresh 0.2"], ["SCREEN --screen /other --refresh 0.2"]],
                         self.screens(done))
        self.assertEqual(["--screen /proj --refresh 0.2", "--path 2", "--screen /other --refresh 0.2"],
                         self.calls())

    def test_a_digit_with_no_loop_keeps_the_folder_or_the_default(self):
        for start, screen in (("/proj", "--screen /proj --refresh 0.2"), ("", "--screen --refresh 0.2")):
            with self.subTest(start=start):
                self.sh(*([start] if start else []), keys="3")
                self.assertEqual([screen, "--path 3", screen], self.calls())

    def test_a_digit_takes_the_folder_a_fresh_path_gives_not_the_one_the_last_screen_showed(self):
        self.path(1, "/fresh")
        self.sh("/proj", keys="1")
        self.assertEqual(["--screen /proj --refresh 0.2", "--path 1", "--screen /fresh --refresh 0.2"],
                         self.calls())

    def test_a_failing_path_does_not_select_what_it_printed(self):
        done = self.sh("/proj", keys="1", status="1")
        self.assertEqual(0, done.returncode)
        self.assertEqual("--screen /proj --refresh 0.2", self.calls()[2])

    def test_f_cycles_through_the_four_filters_and_back(self):
        self.sh("/proj", keys="fffff")
        self.assertEqual(["-", "built", "open", "attention", "-", "built"], self.filters())

    def test_an_unknown_key_only_refreshes(self):
        self.sh("/proj", keys="x")
        self.assertEqual(["--screen /proj --refresh 0.2"] * 2, self.calls())

    def test_zero_and_a_tenth_loop_are_no_selection(self):
        self.path(0, "/zero")
        self.path(10, "/tenth")
        done = self.sh("/proj", keys="10")
        self.assertEqual(3, len(self.screens(done)))
        self.assertEqual(["--screen /proj --refresh 0.2", "--path 1", "--screen /proj --refresh 0.2",
                          "--screen /proj --refresh 0.2"], self.calls())

    def test_q_stops_with_the_message_and_status_0_and_reads_no_more(self):
        done = self.sh("/proj", keys="fqf")
        self.assertEqual((0, 2), (done.returncode, len(self.screens(done))))
        self.assertTrue(done.stdout.endswith("SCREEN --screen /proj --only built --refresh 0.2\n"
                                             "stopped watching.\n"))
        self.assertEqual(["-", "built"], self.filters())

    def test_piped_keys_run_one_by_one_and_the_end_of_input_stops(self):
        done = self.sh("/proj", keys="fx2f")
        self.assertEqual((0, 5), (done.returncode, len(self.screens(done))))
        self.assertEqual(["-", "built", "built", "built", "open"], self.filters())

    def test_the_commands_never_read_the_keys(self):
        done = self.sh("/proj", keys="ff")
        self.assertEqual(3, len(self.screens(done)))
        self.assertEqual("", (self.dir / "stdin").read_text())

    def test_a_failing_command_is_shown_as_it_is_and_the_screen_goes_on_refreshing(self):
        done = self.sh("/proj", keys="xx", status="1")
        self.assertEqual((0, 3), (done.returncode, len(self.screens(done))))
        self.assertEqual(3, done.stdout.count(f"{FAILED}\n"))

    def test_a_single_look_exits_with_the_status_of_a_failing_command(self):
        done = self.sh("-1", status="3")
        self.assertEqual((3, f"{FAILED}\n"), (done.returncode, done.stdout))

    def test_with_no_loop_the_key_line_shows_and_a_refresh_other_than_15_is_said(self):
        for refresh, every in (("0.3", "0.3"), ("", "15")):
            with self.subTest(refresh=refresh):
                done = self.sh(refresh=refresh, fake=False)
                self.assertEqual(0, done.returncode)
                self.assertEqual(["no lean loops running", "",
                                  f"keys: 1-9 switch loop · f filter (all) · q quit · every {every}s"],
                                 self.screens(done)[0])

    def test_the_real_screen_switches_between_folders_that_are_not_projects_and_goes_on(self):
        line = "%d 60 python3 graph/lean.py --workspace /w --repo /nowhere/%s --spec /s/a.md\n"
        done = self.sh(keys="2x", fake=False, ps=line % (10, "first") + line % (20, "second"))
        shown = ["\n".join(text) for text in self.screens(done)]
        self.assertEqual(3, len(shown))
        self.assertIn("not a project with docs/lean: /nowhere/first", shown[0])
        self.assertIn("not a project with docs/lean: /nowhere/second", shown[1])
        self.assertIn("not a project with docs/lean: /nowhere/second", shown[2])

    def test_a_checkout_whose_path_has_spaces_still_runs_the_real_command(self):
        spaced = pathlib.Path(tempfile.mkdtemp()) / "my repos"
        spaced.mkdir()
        (spaced / "graph").symlink_to(GRAPH)
        done = self.sh("-1", script=spaced / "graph" / "loops.sh", fake=False)
        self.assertEqual((0, "no lean loops running\n"), (done.returncode, done.stdout))
        live = self.sh(script=spaced / "graph" / "loops.sh", fake=False)
        self.assertIn("no lean loops running", live.stdout)

    def test_the_script_starts_nothing_but_the_command_and_writes_nothing(self):
        self.path(1, "/fresh")
        self.sh("/proj", keys="1f")
        self.sh("-1", "/proj")
        self.assertEqual([], list(self.here.iterdir()))
        self.assertTrue(all(call.startswith(("--screen", "--path")) for call in self.calls()))


EXPECTED_TESTS = 18


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
