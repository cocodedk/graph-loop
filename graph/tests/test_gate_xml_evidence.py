"""JUnit evidence follows the same reason through retries, cards and stalls."""

import unittest

from test_gate_xml import CONSOLE, HEADING, REPORT, command
from test_loop import Fakes, loop_for, task
from turn import stood_down
from watchdog_spin import ending_signature, spinning

# The fake repository ignores test caches, just as a Gradle project ignores build/.
GATE = command(
    "import xml.etree.ElementTree as ET\n"
    "suite = ET.Element('testsuite')\n"
    "case = ET.SubElement(suite, 'testcase', classname='example.Tests', "
    "name=Path('a.py').read_text().strip())\n"
    "ET.SubElement(case, 'failure', type='NotImplementedError', message='not implemented')\n"
    f"report = Path({('.pytest_cache/' + REPORT)!r})\n"
    "report.parent.mkdir(parents=True, exist_ok=True)\n"
    "ET.ElementTree(suite).write(report)\n",
    console="runner detail\n" * 200 + CONSOLE)


class GateXmlEvidenceTest(unittest.TestCase):
    def test_different_tests_are_distinct_until_the_same_test_fails_twice(self):
        fakes = Fakes(edit="first")
        loop, book, space = loop_for(task(gate=GATE), fakes)
        first = loop.run_task(book.task("T1")).why
        self.assertIn("example.Tests.first: NotImplementedError", first)
        self.assertGreater(len(first), 2000)
        self.assertEqual([first], book.task("T1")["rejections"])
        queued = [row for row in space.events() if row["kind"] == "rebuild_queued"]
        self.assertEqual(first, queued[-1]["why"])
        fakes.edit = "second"
        second = loop.run_task(book.task("T1")).why
        self.assertIn(first, fakes.prompts[-1])
        self.assertFalse(space.needs_slice("T1"))
        self.assertIsNone(spinning(space.events()))
        self.assertEqual("todo", book.task("T1")["status"])
        fakes.edit = "first"
        loop.run_task(book.task("T1"))
        self.assertEqual("needs_slice", book.task("T1")["status"])
        self.assertEqual(first, book.task("T1")["refused_why"])
        failures = [row for row in space.events() if row["kind"] == "failed"]
        self.assertEqual([first, second, first], [row["why"] for row in failures])
        self.assertNotEqual(ending_signature(failures[0]), ending_signature(failures[1]))
        self.assertEqual(ending_signature(failures[0]), ending_signature(failures[2]))
        self.assertEqual("T1", spinning(space.events())[0])
        self.assert_draft(space, first)

    def test_retry_cap_keeps_the_digest_on_the_card_event_and_draft(self):
        fakes = Fakes()
        loop, book, space = loop_for(task(gate=GATE), fakes)
        for name in ("first", "second", "third"):
            fakes.edit = name
            why = loop.run_task(book.task("T1")).why
        self.assertEqual("rejected", book.task("T1")["status"])
        self.assertEqual(why, book.task("T1")["refused_why"])
        rejected = [row for row in space.events() if row["kind"] == "rejected"]
        self.assertEqual(why, rejected[-1]["why"])
        self.assert_draft(space, why)

    def test_red_first_refusal_keeps_the_digest_on_the_card_event_and_draft(self):
        loop, book, space = loop_for(task(gate=GATE, expect_red="different error"), Fakes())
        result = loop.run_task(book.task("T1"))
        self.assertEqual("refused", result.state)
        self.assertIn("example.Tests.one: NotImplementedError", result.why)
        digest = HEADING + result.why.split(HEADING)[1]
        self.assertTrue(book.task("T1")["refused_why"].endswith(digest))
        refused = [row for row in space.events() if row["kind"] == "refused"]
        self.assertEqual(book.task("T1")["refused_why"], refused[-1]["why"])
        # Unprovable cards are exported when the watchdog detects their repeated ending.
        from issue_drafts import draft_stalls
        draft_stalls(space, repeated="T1")
        self.assert_draft(space, result.why)

    def assert_draft(self, space, why):
        stood_down(space, 78, "nothing startable")
        body = next((space.root / "issues").glob("*.md")).read_text()
        _, digest = why.split(HEADING)
        self.assertIn("    " + CONSOLE.splitlines()[0], body)
        for line in digest.splitlines():
            self.assertIn("    " + line, body)
        self.assertIn("    JUnit failures:", body)
