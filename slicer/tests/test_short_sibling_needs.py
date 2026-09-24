"""Short answer-local names resolve without stealing existing dependencies."""

import pathlib
import tempfile
import unittest

import test_contracts_answer_needs as fixtures
import tmp_root  # noqa: F401
from backlog import Backlog
from tree import publish


class ShortSiblingNeedsTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.AnswerNeedsTest()
        self.fixture.setUp()

    def test_short_and_qualified_siblings_publish_the_same_wait(self):
        for dependency in ("schema", "greeting.schema"):
            with self.subTest(dependency=dependency):
                self.fixture.atoms[1]["needs"] = [dependency]
                made = self.fixture.check()["molecule"]
                self.assertEqual([], made["atoms"][1]["needs"])
                backlog = pathlib.Path(tempfile.mkdtemp())
                publish(backlog, made)
                self.assertEqual(["greeting.schema"],
                                 Backlog(backlog).task("greeting.reader")["needs"])

    def test_existing_external_id_wins_over_a_short_alias(self):
        self.fixture.atoms[1]["needs"] = ["schema", "greeting.schema"]
        self.fixture.check(rows=[{"id": "schema"}])
        self.assertEqual(["schema"], self.fixture.atoms[1]["needs"])

    def test_short_self_reference_is_still_a_cycle(self):
        self.fixture.atoms[0]["needs"] = ["schema"]
        with self.assertRaisesRegex(ValueError, "circle"):
            self.fixture.check()

    def test_unknown_name_is_named_in_the_refusal(self):
        self.fixture.atoms[1]["needs"] = ["missing-schema"]
        with self.assertRaisesRegex(ValueError, "missing-schema"):
            self.fixture.check()

    def test_short_forward_sibling_defers_to_stage_order(self):
        self.fixture.atoms[0]["needs"] = ["reader"]
        self.fixture.check()
        self.assertEqual([], self.fixture.atoms[0]["needs"])


if __name__ == "__main__":
    unittest.main()
