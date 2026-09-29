"""Which processes are lean loops, and the project and spec each names."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import loops_ps
import tmp_root  # noqa: F401

HEADER = "    PID ELAPSED COMMAND\n"
ARGS = "--workspace /w/ws --repo /r/sitrep --spec /s/01-capture-core.md"


def find(*lines, cwd=None):
    """The loops in a fake `ps` listing; `cwd` maps a process id to its working directory."""
    text = HEADER + "".join(line + "\n" for line in lines)
    return loops_ps.loops_in(text, (cwd or {}).get)


class Which(unittest.TestCase):
    def test_an_interpreter_running_lean_py_with_the_three_arguments_counts(self):
        self.assertEqual(1, len(find(f"  10  60 python3 /x/graph/lean.py {ARGS}")))
        self.assertEqual(1, len(find(f"  10  60 /usr/bin/python3.12 -u /x/graph/lean.py {ARGS}")))

    def test_interpreter_options_before_the_script_do_not_hide_it(self):
        for options in ("-X dev", "-W ignore -u", "-B -Xdev", "-X utf8 -X dev"):
            with self.subTest(options=options):
                self.assertEqual(1, len(find(f"  10  60 python3 {options} graph/lean.py {ARGS}")))

    def test_a_path_with_spaces_stays_whole(self):
        (loop,) = find("  10  60 python3 /my tools/graph/lean.py --workspace /w s/ws "
                       "--repo /my repos/sitrep --spec /my specs/01 a.md")
        self.assertEqual(("sitrep", "01 a", "/w s/ws"), loop[2:])

    def test_a_relative_path_counts(self):
        self.assertEqual(1, len(find(f"  10  60 python3 graph/lean.py {ARGS}")))
        self.assertEqual(1, len(find(f"  10  60 python3 lean.py {ARGS}")))

    def test_a_shell_that_only_mentions_lean_py_does_not(self):
        self.assertEqual([], find(f"  10  60 bash -c python3 /x/graph/lean.py {ARGS}",
                                  f"  11  60 sh lean.py {ARGS}",
                                  f"  12  60 tail -f /x/graph/lean.py {ARGS}"))

    def test_another_script_or_no_interpreter_does_not(self):
        self.assertEqual([], find(f"  10  60 python3 /x/graph/notlean.py {ARGS}",
                                  f"  11  60 python3 -m unittest lean.py {ARGS}",
                                  f"  12  60 /x/graph/lean.py {ARGS}",
                                  "  13  60 "))

    def test_a_lean_py_without_one_of_the_arguments_does_not(self):
        self.assertEqual([], find("  10  60 python3 lean.py --workspace /w --repo /r",
                                  "  11  60 python3 lean.py --workspace /w --spec /s.md",
                                  "  12  60 python3 lean.py --repo /r --spec /s.md",
                                  "  13  60 python3 lean.py --workspace /w --repo /r --spec"))

    def test_the_header_and_lines_that_are_not_processes_are_skipped(self):
        self.assertEqual([], find("garbage", "  x  y python3 lean.py " + ARGS))

    def test_the_project_and_the_spec_of_absolute_paths(self):
        (loop,) = find(f"  10  60 python3 lean.py {ARGS}")
        self.assertEqual((10, 60, "sitrep", "01-capture-core", "/w/ws"), loop)

    def test_a_trailing_slash_and_an_equals_sign_still_name_the_project(self):
        (loop,) = find("  10  60 python3 lean.py --workspace=/w/ws --repo=/r/sitrep/ --spec=a.md")
        self.assertEqual(("sitrep", "a", "/w/ws"), loop[2:])

    def test_the_project_and_the_spec_of_relative_paths(self):
        (loop,) = find("  10  60 python3 lean.py --workspace ws --repo ../fits-api --spec specs/02f-routes.md",
                       cwd={10: "/work/tool"})
        self.assertEqual(("fits-api", "02f-routes", "/work/tool/ws"), loop[2:])

    def test_an_absolute_path_is_used_as_it_is_when_the_working_directory_cannot_be_read(self):
        (loop,) = find(f"  10  60 python3 lean.py {ARGS}", cwd={})
        self.assertEqual(("sitrep", "01-capture-core", "/w/ws"), loop[2:])

    def test_a_relative_repo_shows_its_project_as_a_question_mark_without_the_working_directory(self):
        (loop,) = find("  10  60 python3 lean.py --workspace /w/ws --repo ../fits-api --spec s.md", cwd={})
        self.assertEqual(("?", "s", "/w/ws"), loop[2:])

    def test_a_relative_workspace_is_unreadable_without_the_working_directory(self):
        (loop,) = find("  10  60 python3 lean.py --workspace ws --repo /r/sitrep --spec s.md", cwd={})
        self.assertEqual(("sitrep", "s", None), loop[2:])

    def test_the_loops_come_by_process_id_from_the_lowest(self):
        loops = find(f"  30  60 python3 lean.py {ARGS}", f"   4  60 python3 lean.py {ARGS}",
                     f"  12  60 python3 lean.py {ARGS}")
        self.assertEqual([4, 12, 30], [loop.pid for loop in loops])


EXPECTED_TESTS = 15


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
