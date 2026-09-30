"""A gate that runs its interpreter by full path grants that spelling too. Claude Code matches a
command as written, so a builder told `Bash(python *)` was denied `/venv/bin/python tests/run.py`
and could run neither its tests nor its helpers (issue #220)."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import code_grant
import gate_programs
import tmp_root  # noqa: F401

EXPECTED_TESTS = 10


def grants(gate: str) -> list[str]:
    shell = code_grant.code_shell({"gate": gate})
    return shell.removeprefix(code_grant.BASE_SHELL).split(",")


class PathGrant(unittest.TestCase):
    def test_a_path_to_the_interpreter_is_granted_beside_its_name(self):
        shell = grants("/venv/bin/python tests/run.py")
        self.assertIn("Bash(python *)", shell)
        self.assertIn("Bash(/venv/bin/python *)", shell)

    def test_a_relative_path_is_granted_beside_its_name(self):
        shell = grants("./run.sh")
        self.assertIn("Bash(run.sh *)", shell)
        self.assertIn("Bash(./run.sh *)", shell)

    def test_an_unsafe_path_is_granted_by_its_name_only(self):
        for gate in ('"/my venv/bin/python" t.py', "'/v/it'\"'\"'s/python' t.py",
                     "$VENV/bin/python t.py", "/v/$X/python t.py"):
            with self.subTest(gate=gate):
                shell = grants(gate)
                self.assertIn("Bash(python *)", shell)
                self.assertEqual(1, sum(part.endswith("python *)") for part in shell))

    def test_a_floor_program_gets_no_grant_by_any_spelling(self):
        shell = grants("/bin/bash tests/run.sh\n./sudo x\n/usr/bin/curl y")
        for name in ("bash", "sudo", "curl"):
            self.assertFalse([part for part in shell if part.endswith(f"{name} *)")])

    def test_a_path_written_twice_is_granted_once(self):
        shell = grants("/venv/bin/python a.py && /venv/bin/python b.py && python c.py")
        self.assertEqual(["Bash(python *)", "Bash(/venv/bin/python *)"], shell[-2:])
        self.assertEqual(1, shell.count("Bash(/venv/bin/python *)"))

    def test_a_substitution_and_an_assignment_are_read_as_before(self):
        shell = grants('set -e\nW="$(/opt/bin/mktemp -d)"\nA=1 /venv/bin/python t.py "$W"')
        self.assertIn("Bash(/opt/bin/mktemp *)", shell)
        self.assertIn("Bash(/venv/bin/python *)", shell)

    def test_a_gate_it_cannot_read_adds_no_path_grant(self):
        gate = "/venv/bin/python -c 'import x"
        self.assertEqual([], gate_programs.spellings(gate))
        self.assertEqual(code_grant.code_shell({"gate": gate}).count("Bash(/"), 0)

    def test_bare_names_grant_what_they_did_before_in_the_same_order(self):
        gate = "set -e\njavac -d out A.java && java -cp out T"
        shell = code_grant.code_shell({"gate": gate})
        self.assertTrue(shell.endswith("Bash(javac *),Bash(java *)"))
        self.assertEqual(["javac", "java"], gate_programs.programs(gate))

    def test_programs_reads_the_spec_gates_as_bare_names_in_order(self):
        """Done when #6: the reader says what it always said, whatever the grant does."""
        for gate, names in (
                ("/venv/bin/python tests/run.py", ["python"]),
                ("./run.sh", ["run.sh"]),
                ('"/my venv/bin/python" t.py', ["python"]),
                ("'/v/it'\"'\"'s/python' t.py", ["python"]),
                ("$VENV/bin/python t.py", ["python"]),
                ("/v/$X/python t.py", ["python"]),
                ("/bin/bash tests/run.sh\n./sudo x\n/usr/bin/curl y", ["bash", "sudo", "curl"])):
            with self.subTest(gate=gate):
                self.assertEqual(names, gate_programs.programs(gate))

    def test_programs_still_returns_bare_names(self):
        self.assertEqual(["python", "run.sh", "mktemp"], gate_programs.programs(
            'W="$(mktemp -d)"\n/venv/bin/python a.py && ./run.sh && python b.py'))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
