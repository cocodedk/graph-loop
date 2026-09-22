"""A colon in plain prose gets one local repair, not a paid planning round."""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from contracts import mapping


class YamlRepairTest(unittest.TestCase):
    def test_the_feedback_goal_survives_inside_a_fenced_answer(self):
        goal = "AndroidFeedback(view: View) : Feedback present"
        text = ("Here is the molecule.\n```yaml\nresult: MOLECULE\n"
                "molecule:\n  atoms:\n    - name: feedback\n"
                f"      goal: {goal}\n```\n")
        self.assertEqual(goal, mapping(text)["molecule"]["atoms"][0]["goal"])

    def test_sequence_keys_and_trailing_colons_are_repaired_together(self):
        answer = mapping("atoms:\n  - goal: return value: present\n"
                         "    done_when: the gate proves:\n")
        self.assertEqual([{"goal": "return value: present",
                           "done_when": "the gate proves:"}], answer["atoms"])

    def test_quotes_and_backslashes_remain_literal(self):
        goal = 'the "value" in path\\name: present'
        self.assertEqual(goal, mapping(f"goal: {goal}\n")["goal"])

    def test_other_yaml_value_styles_are_unchanged_during_repair(self):
        for value in ('"value: present"', "'value: present'", "[one, two]",
                      "{one: two}", "|\n  line: present", ">\n  line: present"):
            with self.subTest(value=value):
                original = f"note: {value}\n"
                answer = mapping(original + "goal: return value: present\n")
                self.assertEqual(yaml.safe_load(original)["note"], answer["note"])

    def test_literal_gate_lines_are_not_rewritten_as_yaml_keys(self):
        text = ("atoms:\n  - gate: |\n      command: argument: value\n"
                "    goal: return value: present\n")
        self.assertEqual("command: argument: value\n",
                         mapping(text)["atoms"][0]["gate"])

    def test_an_unrelated_scanner_error_names_the_whole_original_line(self):
        line = "  goal: @" + "a long sentence " * 12
        with self.assertRaises(ValueError) as caught:
            mapping("molecule:\n" + line + "\n")
        self.assertIn("the answer is not YAML", str(caught.exception))
        self.assertIn("line 2:\n" + line, str(caught.exception))

    def test_a_failed_repair_names_the_original_parser_error_line(self):
        line = "  note: " + "a long sentence " * 12
        with self.assertRaises(ValueError) as caught:
            mapping("goal: return value: present\nmolecule:\n  atoms: [one\n" + line)
        self.assertIn("line 4:\n" + line, str(caught.exception))

    def test_valid_yaml_is_only_parsed_once(self):
        with mock.patch("contracts.yaml.safe_load", wraps=yaml.safe_load) as parse:
            self.assertEqual({"goal": "present"}, mapping("goal: present"))
        self.assertEqual(1, parse.call_count)

    def test_an_invalid_answer_gets_only_one_local_retry(self):
        with mock.patch("contracts.yaml.safe_load", wraps=yaml.safe_load) as parse, \
                self.assertRaises(ValueError):
            mapping("goal: value: present\nnote: @invalid\n")
        self.assertEqual(2, parse.call_count)


if __name__ == "__main__":
    unittest.main()
