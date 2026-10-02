"""A crashed Codex call keeps its error: the banner is first in what it prints, the error last.

The text used to be the first 500 characters, which with empty stdout was only the banner.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401
from provider_codex import codex_text
from test_providers import fake

EXPECTED_TESTS = 4
ERROR = "Error: the model is not available to this account"


def call(script):
    return codex_text(fake(script), "question", model="m", effort="medium", cwd="", timeout=30)


class CrashText(unittest.TestCase):
    def test_a_long_stderr_ends_with_its_last_500_characters_and_shows_the_error_line(self):
        out = call(f"for i in $(seq 1 60); do echo 'banner line '$i >&2; done; echo '{ERROR}' >&2; "
                   "for i in $(seq 1 30); do echo 'trailing note '$i >&2; done; exit 1")
        self.assertEqual("crash", out.kind)
        self.assertTrue(out.text.startswith(ERROR + "\n\n"))
        self.assertTrue(out.text.endswith("trailing note 30"))
        self.assertNotIn("banner line 1\n", out.text)
        self.assertEqual(ERROR + "\n\n" + out.raw.strip()[-500:], out.text)

    def test_an_error_line_already_in_the_last_500_characters_is_not_repeated(self):
        out = call(f"for i in $(seq 1 60); do echo 'banner line '$i >&2; done; echo '{ERROR}' >&2; exit 1")
        self.assertEqual(out.raw.strip()[-500:], out.text)
        self.assertEqual(1, out.text.count(ERROR))

    def test_short_output_is_kept_whole_and_stdout_is_preferred(self):
        self.assertEqual(ERROR, call(f"echo '{ERROR}' >&2; exit 1").text)
        self.assertEqual("partial answer", call("echo 'partial answer'; echo noise >&2; exit 1").text)

    def test_a_successful_call_keeps_its_text(self):
        out = call(f"echo '{'x' * 900}'; echo {ERROR} >&2")
        self.assertEqual(("x" * 900) + "\n", out.text)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
