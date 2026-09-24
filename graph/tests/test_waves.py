"""The frontier projected forward: what would run together, wave after wave.

The owner's rule this serves: the graph assigns a new agent each time it
branches out, as many as there are branches. The loop already runs one thread
per startable card — what it lacked was the view, so nobody could see how wide
the graph gets or where the lane cap costs a turn.

A wave is a SNAPSHOT: the backlog is re-sliced between runs, so every line says
so. A held card is listed as held and never scheduled.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import frontier
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import waves

EXPECTED_TESTS = 13


def card(task_id: str, needs=(), files=None, **fields) -> dict:
    return {"id": task_id, "goal": "g", "status": "todo", "needs": list(needs),
            "files": [f"{task_id}.py"] if files is None else list(files),
            "gate": "true", "done_when": "x", **fields}


def seen(rows: list[dict]) -> list[list[str]]:
    """The ids of each projected wave: what these tests are about."""
    return [waves.ids(wave) for wave in waves.project(rows)]


def one_file() -> list[dict]:
    """Two cards that both write `shared.py`: two lanes would overwrite each other."""
    return [card("T1", files=["shared.py"]), card("T2", files=["shared.py"])]


class ProjectionTest(unittest.TestCase):
    def test_a_wave_releases_the_cards_that_waited_on_it(self):
        rows = [card("T1"), card("T2"), card("T3", needs=["T1"]),
                card("T4", needs=["T1", "T3"])]
        self.assertEqual([["T1", "T2"], ["T3"], ["T4"]], seen(rows))

    def test_the_projection_writes_nothing_back(self):
        rows = [card("T1"), card("T2", needs=["T1"])]
        waves.project(rows)
        self.assertEqual(["todo", "todo"], [row["status"] for row in rows])

    def test_a_card_that_nothing_can_start_gets_no_wave(self):
        rows = [card("T1", status="rejected"), card("T2", needs=["T1"])]
        self.assertEqual([], seen(rows))

    def test_what_another_agent_holds_narrows_only_the_first_wave(self):
        # `status` prints this beside its "ready now" line, which is read with
        # the same claims, so the first wave has to agree with it.
        rows = [card("T1"), card("T2")]
        self.assertEqual([["T2"], ["T1"]],
                         [waves.ids(wave) for wave in waves.project(rows, running=["T1"])])


class OverlapTest(unittest.TestCase):
    """The control: a projection that ignores file overlap is not this one."""

    def test_two_cards_on_one_file_are_two_waves(self):
        self.assertEqual([["T1"], ["T2"]], seen(one_file()))

    def test_a_projection_that_ignores_file_overlap_is_shown_to_fail(self):
        # The check exists to catch exactly this, so it is made to fail here
        # first: with the disjointness rule taken out, the two cards that share
        # `shared.py` are scheduled in the same wave — two lanes overwriting
        # each other — and the assertion above goes red on it.
        with unittest.mock.patch.object(frontier, "overlap", return_value=False):
            naive = seen(one_file())
        self.assertEqual([["T1", "T2"]], naive)
        with self.assertRaises(AssertionError):
            self.assertEqual([["T1"], ["T2"]], naive)


class HeldTest(unittest.TestCase):
    def test_a_held_card_is_listed_as_held_and_never_scheduled(self):
        rows = [card("T1"), card("T9", blocked_by_human=True), card("T10", needs=["T9"])]
        self.assertEqual([["T1"]], seen(rows))
        self.assertEqual(["T9"], waves.held(rows))
        self.assertIn("held on the card, never scheduled: T9", waves.as_text(rows))

    def test_a_hold_on_finished_work_is_not_news(self):
        rows = [card("T9", status="done", blocked_by_human=True)]
        self.assertEqual([], waves.held(rows))


class AloneTest(unittest.TestCase):
    """A card that runs alone takes a whole turn: the projection has to count
    turns the way the driver spends them, not by dividing cards by the cap."""

    def test_four_cards_that_run_alone_are_four_turns_not_two(self):
        rows = [card(f"L{n}", files=[], gate_has_side_effects=True) for n in range(1, 5)]
        self.assertIn("4 wide, cap 3, 4 turns", waves.as_text(rows, cap=3))

    def test_a_wave_under_the_cap_still_says_so_when_it_costs_turns(self):
        rows = [card("E1", files=[]), card("E2", files=[])]
        self.assertIn("2 wide, cap 3, 2 turns", waves.as_text(rows, cap=3))

    def test_cards_that_run_alone_are_counted_beside_the_lanes(self):
        # One turn for the card that runs alone, two for four code cards at
        # a cap of three — not the five-over-three a flat division gives.
        rows = [card("E1", files=[])] + [card(f"T{n}") for n in range(1, 5)]
        self.assertIn("5 wide, cap 3, 3 turns", waves.as_text(rows, cap=3))


class TextTest(unittest.TestCase):
    def test_a_wave_wider_than_the_cap_says_so_in_the_same_line(self):
        rows = [card(f"T{n}") for n in range(1, 6)] + [card("T6", needs=["T1"])]
        text = waves.as_text(rows, cap=2)
        self.assertIn("wave 1: T1, T2, T3, T4, T5 — 5 wide, cap 2, 3 turns", text)
        self.assertNotIn("wide", text.splitlines()[2])   # wave 2 fits: nothing is said
        self.assertIn("snapshot", text.splitlines()[0])  # labelled as of this moment


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
