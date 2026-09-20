"""The note IS the card: it reads back as it was written, and the loop's own
writes never reach the prose.

Both halves are checked by making the case fail first. A link that is not
turned into the note it names leaves Obsidian's graph empty of edges, and a
status write that rewrites the file loses whatever a person typed under it —
neither shows up as an exception, so each is asserted here.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

CARD = {
    "status": "todo",
    "files": ["signup.py"],
    "gate_reviewed_first": True,
    "goal": "the signup form rejects a blank email",
    "why": "a blank address silently made an account nobody could reach",
    "done_when": "posting an empty email answers 422 and names the field",
    "gate": "set -euo pipefail\npython3 -m unittest tests.test_signup",
    "needs": ["T4", "T4.signin"],
    "uses": ["drive/lib/backlog.py:RUNNABLE"],
    "creates": ["signup.py:def reject_blank"],
    "note": "one form, one rule",
}

EXPECTED_TESTS = 15


def vault() -> pathlib.Path:
    """A vault holding T4 with one atom, so a link has something to resolve to."""
    root = pathlib.Path(tempfile.mkdtemp()) / "vault"
    (root / "T4").mkdir(parents=True)
    for name in (cardfile.HEAD, "01-signin.md"):
        (root / "T4" / name).write_text(cardfile.dump({"status": "todo"}), "utf-8")
    return root


class ANoteReadsBackAsItsCard(unittest.TestCase):
    def test_every_field_survives_the_round_trip(self):
        self.assertEqual(CARD, {key: value for key, value
                                in cardfile.parse(cardfile.dump(CARD)).items()})

    def test_writing_what_was_read_changes_nothing(self):
        once = cardfile.dump(CARD)
        self.assertEqual(once, cardfile.dump(cardfile.parse(once)))

    def test_the_loop_s_own_fields_are_front_matter_and_the_prose_is_not(self):
        front, body = cardfile.dump(CARD).split("---\n")[1], cardfile.dump(CARD)
        self.assertIn("status: todo", front)
        self.assertNotIn("the signup form rejects", front)
        self.assertIn("## Goal", body)

    def test_a_gate_is_one_fenced_block(self):
        self.assertIn("## Gate\n\n```sh\nset -euo pipefail\n", cardfile.dump(CARD))

    def test_a_gate_keeps_its_own_last_newline(self):
        # The loop hashes the gate text to excuse one exact gate, so a newline
        # the note drops is a different gate: it changed every one of them once.
        for gate in ("run", "run\n", "set -e\nrun\n"):
            card = {"status": "todo", "gate": gate}
            self.assertEqual(gate, cardfile.parse(cardfile.dump(card))["gate"])

    def test_text_that_is_not_a_note_is_refused(self):
        with self.assertRaises(ValueError):
            cardfile.parse("goal: the old shape\nstatus: todo\n")


class TheLinksAreTheGraph(unittest.TestCase):
    def test_a_wait_is_written_as_the_note_that_holds_it(self):
        text = cardfile.dump(CARD, cardfile.linker(vault()))
        self.assertIn("- [[T4/molecule]]", text)
        self.assertIn("- [[T4/01-signin]]", text)

    def test_a_linked_wait_still_reads_back_as_its_id(self):
        text = cardfile.dump(CARD, cardfile.linker(vault()))
        self.assertEqual(["T4", "T4.signin"], cardfile.parse(text)["needs"])

    def test_a_name_that_is_no_note_of_this_vault_is_left_alone(self):
        text = cardfile.dump(CARD, cardfile.linker(vault()))
        self.assertIn("- [[drive/lib/backlog.py:RUNNABLE]]", text)
        self.assertEqual(CARD["uses"], cardfile.parse(text)["uses"])


class AFieldWriteLeavesTheBodyAlone(unittest.TestCase):
    def test_a_status_write_touches_nothing_but_the_status(self):
        # Hand-written, with a comment and endings the loop would not produce.
        note = ("---\r\n# mine, do not reformat\r\nstatus: todo\r\n---\r\n\r\n"
                "## Goal\r\n\r\nthe form rejects a blank email\r\n")
        written = cardfile.patch(note, "status", "done")
        self.assertEqual(note.replace("status: todo", "status: done"), written)
        self.assertEqual("done", cardfile.parse(written)["status"])


class AMultiLineFieldSurvivesBeingWritten(unittest.TestCase):
    """The loop wrote its own refusal text into a card and then could not read
    the card back.

    `safe_dump` of a string holding a newline emits a quoted scalar with a BLANK
    line inside it. `patch` found the old value with a regex whose idea of a
    continuation line was "starts with space, tab or dash", so it stopped at
    that blank line and orphaned the tail — the blank line and the closing
    quote. Twice over, the card stopped parsing at all, and `backlog_tree.read`
    loads every card in the vault, so one card took `status`, `plan`, `run`,
    `doctor` and `report` down with it. The trigger is any refusal long enough
    to wrap, written twice, which the loop does to itself (2026-09-18).

    A regex cannot know where a YAML value ends. The parser can, so it is asked.
    """

    LONG = ("validation_refused: the gate writes \"$WORK/Check.java\", which nothing "
            "owns: a gate's output goes to `$(mktemp)`, the home the driver removes\n")

    def test_writing_over_a_wrapped_value_leaves_no_tail_behind(self):
        note = cardfile.dump({"status": "todo", "refused_why": self.LONG, "slices": 1})
        written = cardfile.patch(note, "refused_why", "second refusal")
        self.assertEqual("second refusal", cardfile.parse(written)["refused_why"])
        self.assertEqual("todo", cardfile.parse(written)["status"])
        self.assertEqual(1, cardfile.parse(written)["slices"])

    def test_a_card_written_twice_still_reads(self):
        note = cardfile.dump({"status": "todo", "refused_why": self.LONG, "slices": 1})
        written = cardfile.patch(note, "refused_why", self.LONG.replace("Check", "Second"))
        written = cardfile.patch(written, "slices", 2)
        self.assertEqual(2, cardfile.parse(written)["slices"])          # it used to raise
        self.assertIn("Second", cardfile.parse(written)["refused_why"])

    def test_a_list_field_is_replaced_whole(self):
        note = cardfile.dump({"status": "todo", "waits": ["T1", "T2"], "slices": 1})
        written = cardfile.patch(note, "waits", ["T9"])
        self.assertEqual(["T9"], cardfile.parse(written)["waits"])
        self.assertEqual(1, cardfile.parse(written)["slices"])

    def test_a_wrapped_field_can_be_taken_out(self):
        note = cardfile.dump({"status": "todo", "refused_why": self.LONG, "slices": 1})
        written = cardfile.patch(note, "refused_why", None)
        card = cardfile.parse(written)
        self.assertNotIn("refused_why", card)
        self.assertEqual({"status": "todo", "slices": 1}, card)


class AnUnreadableCardSaysWhichOne(unittest.TestCase):
    def test_the_file_is_named_in_the_error(self):
        """`backlog_tree.read` loads every card in the vault, so one bad card
        stops `status`, `plan`, `run`, `doctor` and `report` alike — and the
        traceback named none of them. Finding it meant walking the vault by
        hand (2026-09-18)."""
        import tempfile
        path = pathlib.Path(tempfile.mkdtemp()) / "molecule.md"
        path.write_text("---\nstatus: todo\nrefused_why: 'unclosed\n---\n", "utf-8")
        with self.assertRaises(ValueError) as caught:
            cardfile.load(path)
        self.assertIn(str(path), str(caught.exception))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
