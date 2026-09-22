"""A failing gate names the cases its runner only counted on the console."""

from __future__ import annotations

import pathlib
import shlex
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401
from gates import prove_red, run_gate

REPORT = "app/build/test-results/testDebugUnitTest/TEST-cases.xml"
CONSOLE = "11 tests completed, 11 failed\nBUILD FAILED in 1s\n"
HEADING = "\n\nJUnit failures:\n"


def xml(names, message="not implemented\nsecond line", kind="failure"):
    suite = ET.Element("testsuite")
    for name in names:
        case = ET.SubElement(suite, "testcase", classname="example.Tests", name=name)
        ET.SubElement(case, kind, type="NotImplementedError", message=message)
    ET.SubElement(suite, "testcase", classname="example.Tests", name="passes")
    ET.SubElement(ET.SubElement(suite, "testcase", name="skips"), "skipped")
    return ET.tostring(suite, encoding="unicode")


def command(body, console=CONSOLE, code=1):
    script = ("from pathlib import Path\nimport os, time\n" + body
              + f"\nprint({console!r}, end='')\nraise SystemExit({code})\n")
    return "python3 -c " + shlex.quote(script)


def write_report(contents, path=REPORT):
    return (f"report = Path({path!r})\nreport.parent.mkdir(parents=True, exist_ok=True)\n"
            f"report.write_text({contents!r})\n")


class GateXmlTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cwd = self.directory.name

    def test_three_failed_cases_are_named_with_type_and_first_message_line(self):
        body = xml(["first", "second", "third"])
        body = body.replace('type="NotImplementedError"', 'type="AssertionError"', 1)
        ok, why = prove_red(command(write_report(body)), self.cwd)
        self.assertTrue(ok)
        self.assertTrue(why.startswith(CONSOLE + HEADING))
        for name, kind in (("first", "AssertionError"), ("second", "NotImplementedError"),
                           ("third", "NotImplementedError")):
            self.assertIn(f"example.Tests.{name}: {kind}: not implemented", why)
        for absent in ("second line", "passes", "skips"):
            self.assertNotIn(absent, why)

    def test_no_report_preserves_the_console_and_its_original_tail(self):
        console = "setup\n" * 500 + CONSOLE
        gate = command("", console)
        self.assertEqual(console, run_gate(gate, self.cwd).output)
        self.assertEqual((True, console[-2000:]), prove_red(gate, self.cwd))

    def test_more_than_twenty_cases_counts_every_omitted_case(self):
        _, why = prove_red(command(write_report(xml([f"case_{n}" for n in range(25)]))), self.cwd)
        self.assertEqual(20, why.count("example.Tests."))
        self.assertIn("example.Tests.case_19:", why)
        self.assertNotIn("example.Tests.case_20:", why)
        self.assertTrue(why.endswith("… and 5 more"))

    def test_character_limit_keeps_a_count_and_the_console_tail(self):
        console = "setup\n" * 500 + CONSOLE
        body = write_report(xml([f"case_{n}" for n in range(8)], message="x" * 700))
        _, why = prove_red(command(body, console), self.cwd)
        tail, digest = why.split(HEADING)
        self.assertEqual(console[-2000:], tail)
        self.assertLessEqual(len(HEADING + digest), 2000)
        shown = digest.count("example.Tests.")
        self.assertGreater(shown, 0)
        self.assertTrue(digest.endswith(f"… and {8 - shown} more"))

    def test_an_earlier_gates_xml_is_not_this_runs_evidence(self):
        run_gate(command(write_report(xml(["stale"]))), self.cwd)
        self.assertEqual((True, CONSOLE), prove_red(command(""), self.cwd))

    def test_newest_files_come_first_with_path_order_breaking_mtime_ties(self):
        body = "stamp = time.time_ns()\n"
        for name, age in (("older", 0), ("newer_b", 10), ("newer_a", 10)):
            body += write_report(xml([name]), REPORT.replace("cases", name))
            body += f"os.utime(report, ns=(stamp + {age}, stamp + {age}))\n"
        _, why = prove_red(command(body), self.cwd)
        self.assertLess(why.index("newer_a"), why.index("newer_b"))
        self.assertLess(why.index("newer_b"), why.index("older"))

    def test_error_elements_and_message_text_are_read_too(self):
        body = ('<testsuite><testcase classname="example.Tests" name="broken">'
                '<error type="RuntimeError">first line\ntraceback</error>'
                '</testcase></testsuite>')
        _, why = prove_red(command(write_report(body)), self.cwd)
        self.assertIn("example.Tests.broken: RuntimeError: first line", why)
        self.assertNotIn("traceback", why)

    def test_red_first_can_match_the_failure_type_only_found_in_xml(self):
        ok, why = prove_red(command(write_report(xml(["stub"]))), self.cwd,
                            expect="NotImplementedError")
        self.assertTrue(ok, why)

    def test_digest_uses_the_draft_scrubber_before_it_becomes_evidence(self):
        message = f"missing {self.cwd}/private/input.txt"
        _, why = prove_red(command(write_report(xml(["private"], message))), self.cwd)
        self.assertIn("missing [path]", why)
        self.assertNotIn(self.cwd, why)

    def test_malformed_or_successful_reports_do_not_change_the_evidence(self):
        for body in ("<testsuite", '<testsuite><testcase name="passes"/></testsuite>'):
            with self.subTest(xml=body):
                self.assertEqual((True, CONSOLE),
                                 prove_red(command(write_report(body)), self.cwd))

    def test_a_green_gate_does_not_append_a_report(self):
        result = run_gate(command(write_report(xml(["old_failure"])), code=0), self.cwd)
        self.assertTrue(result.passed)
        self.assertEqual(CONSOLE, result.output)
