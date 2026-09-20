"""An atom may not name what nothing has made yet.

The four cases below are the four real ones. Each cost the loop a day: a card
named a thing, the thing did not exist, and every attempt at the card was
refused for a reason no builder could fix.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import molecule
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit


def repo(files: dict[str, str]) -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp())
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, "utf-8")
    return root


EXPECTED_TESTS = 15


class TheFourThatCostUsADay(unittest.TestCase):
    def setUp(self):
        # The product as it stands: the scheduler builds a story of items and
        # integrity, and the campaign writes an observation event with no verdict.
        self.look = molecule.present(repo({
            "simulation/scheduler/app.py": 'story = {"items": items, "integrity": {}}',
            "simulation/campaign/app.py": 'record("OBSERVATION_RECORDED", window=w)',
            "models.py": 'BUILDERS = ("claude-opus-5", "claude-sonnet-5")'}))

    def refused(self, *names):
        return molecule.unavailable([{"id": "a", "uses": list(names)}], self.look)

    def test_a_durable_field_no_producer_emits_is_refused(self):
        self.assertEqual(
            self.refused("simulation/scheduler/app.py:outcome_facts"),
            [("a", "simulation/scheduler/app.py:outcome_facts")])

    def test_a_field_the_story_does_not_carry_is_refused(self):
        self.assertEqual(
            self.refused("simulation/scheduler/app.py:observation"),
            [("a", "simulation/scheduler/app.py:observation")])

    def test_a_model_the_binary_does_not_accept_is_refused(self):
        self.assertEqual(self.refused("models.py:gpt-5.6-sol"),
                         [("a", "models.py:gpt-5.6-sol")])

    def test_an_event_that_is_written_passes_whatever_it_means(self):
        # The law is about existence. That OBSERVATION_RECORDED carries no
        # verdict is a matter for the card's own gate, not for this rule.
        self.assertEqual(self.refused("simulation/campaign/app.py:OBSERVATION_RECORDED"), [])

    def test_a_name_in_a_file_that_is_not_there_is_refused(self):
        self.assertEqual(self.refused("simulation/nowhere.py:items"),
                         [("a", "simulation/nowhere.py:items")])

    def test_what_the_product_carries_passes(self):
        self.assertEqual(self.refused("simulation/scheduler/app.py:items",
                                      "simulation/scheduler/app.py:integrity"), [])


class AnEarlierAtomIsTheLicence(unittest.TestCase):
    def setUp(self):
        self.look = molecule.present(repo({"app.py": "nothing here"}))

    def test_the_atom_that_creates_it_first_licenses_the_one_that_uses_it(self):
        self.assertEqual(molecule.unavailable([
            {"id": "01-schema", "creates": ["app.py:observation"]},
            {"id": "02-reader", "uses": ["app.py:observation"]}], self.look), [])

    def test_the_same_two_in_the_wrong_order_are_refused(self):
        self.assertEqual(molecule.unavailable([
            {"id": "02-reader", "uses": ["app.py:observation"]},
            {"id": "01-schema", "creates": ["app.py:observation"]}], self.look),
            [("02-reader", "app.py:observation")])

    def test_an_atom_may_read_back_what_it_writes(self):
        self.assertEqual(molecule.unavailable([
            {"id": "01", "creates": ["app.py:observation"],
             "uses": ["app.py:observation"]}], self.look), [])


class NothingOutsideTheRepositoryIsAName(unittest.TestCase):
    def setUp(self):
        self.root = repo({"app.py": "here"})
        self.look = molecule.present(self.root)
        (self.root.parent / "elsewhere.py").write_text("here", "utf-8")

    def test_an_absolute_path_is_not_there(self):
        self.assertFalse(self.look("/etc/hostname:."))

    def test_a_path_that_climbs_out_is_not_there(self):
        self.assertFalse(self.look("../elsewhere.py:here"))

    def test_a_path_inside_still_is(self):
        self.assertTrue(self.look("app.py:here"))


class ACreatesThatIsNotAName(unittest.TestCase):
    def test_it_licenses_nothing_and_says_so(self):
        look = molecule.present(repo({"app.py": "here"}))
        with self.assertRaises(ValueError):
            molecule.unavailable([{"id": "01", "creates": ["observation"],
                                   "uses": ["observation"]}], look)


class ANameIsAPathAndText(unittest.TestCase):
    def test_a_bare_word_is_not_a_name(self):
        with self.assertRaises(ValueError):
            molecule.split("outcome_facts")

    def test_the_path_and_the_text_come_back_apart(self):
        self.assertEqual(molecule.split("a/b.py:some text: with a colon"),
                         ("a/b.py", "some text: with a colon"))


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
