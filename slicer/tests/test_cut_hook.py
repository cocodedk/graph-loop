"""The hook forwards a molecule with its bound arguments to the checker and adds nothing."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from cut_hook import make_checker

EXPECTED_TESTS = 3


class CutHook(unittest.TestCase):
    def test_forwards_every_argument_and_returns_the_result_unchanged(self):
        calls = []
        result = object()

        def check(molecule, campaign, space, ask, wall=None):
            calls.append((molecule, campaign, space, ask, wall))
            return result

        ask, molecule = object(), {"atoms": []}
        got = make_checker("camp", "space", ask, wall="wall", check=check)(molecule)
        self.assertIs(got, result)
        self.assertEqual(calls, [(molecule, "camp", "space", ask, "wall")])

    def test_wall_defaults_to_none(self):
        seen = []
        make_checker("c", "s", None, check=lambda m, c, s, a, wall=None: seen.append(wall))({})
        self.assertEqual(seen, [None])

    def test_each_call_forwards_its_own_molecule(self):
        seen = []
        checker = make_checker("c", "s", None, check=lambda m, *a, **k: seen.append(m))
        checker(1)
        checker(2)
        self.assertEqual(seen, [1, 2])


if __name__ == "__main__":
    unittest.main()
