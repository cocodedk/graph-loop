"""No line of code outside the block in `lib/models.py` names a lean model or effort, and the model the
owner replaced on 2026-09-30 is named only where a dated comment records what was decided then."""

import ast
import pathlib
import re
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401

EXPECTED_TESTS = 2
ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCK = "graph/lib/models.py"
LEAN_MODELS = ("gpt-6.1-sol", "claude-sonnet-5-5")
LEAN_EFFORTS = ("high", "xhigh")
LEAN_FILES = ("graph/lean_run.py", "graph/lean_calls.py", "graph/lib/providers.py", "graph/lib/review.py",
              "graph/lib/resources.py")
REPLACED = "gpt-6" + "-sol"   # spelled in two pieces, so this file does not name it
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def tracked() -> list[str]:
    """Every file the repository tracks, and the new ones not yet added (a fixpoint commits them)."""
    listed = subprocess.run(("git", "ls-files", "--cached", "--others", "--exclude-standard"),
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted(set(listed.splitlines()))


def literals(name: str) -> list[tuple[int, str]]:
    """The (line, text) of every string in the code of a file that is not a docstring."""
    tree = ast.parse((ROOT / name).read_text("utf-8"))
    docs = {id(node.body[0].value) for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and ast.get_docstring(node)}
    return [(node.lineno, node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs]


def dated_comment(lines: list[str], at: int) -> bool:
    """Whether line `at` is a comment in a run of comment lines where one carries a date."""
    if not lines[at].lstrip().startswith("#"):
        return False
    first, last = at, at
    while first > 0 and lines[first - 1].lstrip().startswith("#"):
        first -= 1
    while last + 1 < len(lines) and lines[last + 1].lstrip().startswith("#"):
        last += 1
    return any(DATE.search(line) for line in lines[first:last + 1])


class NoLiterals(unittest.TestCase):
    def test_no_code_outside_the_block_names_a_lean_model_or_effort(self):
        hits = []
        for name in tracked():
            if name.endswith(".py") and name != BLOCK and "tests" not in pathlib.PurePath(name).parts:
                hits += [f"{name}:{line}" for line, text in literals(name)
                         if any(model in text for model in LEAN_MODELS)]
        for name in LEAN_FILES:
            hits += [f"{name}:{line}" for line, text in literals(name) if text in LEAN_EFFORTS]
        self.assertEqual([], hits)

    def test_the_replaced_model_is_named_only_in_a_dated_comment_or_the_spec(self):
        hits = []
        for name in tracked():
            path = ROOT / name
            if not path.is_file() or name.startswith("docs/lean/07-"):
                continue
            lines = path.read_text("utf-8", errors="ignore").splitlines()
            hits += [f"{name}:{number + 1}" for number, line in enumerate(lines)
                     if REPLACED in line and not dated_comment(lines, number)]
        self.assertEqual([], hits)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
