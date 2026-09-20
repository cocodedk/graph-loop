"""An empty backlog is not a finished campaign.

astra's review, finding 12: with approved sources declared and their coverage
never accepted, `run` returned 0 on an empty backlog — and `supervisor.sh`
reads rc 0 as "the backlog is worked out" and stands down for good. So a
campaign whose planning failed looked exactly like one whose work was done.

Codex's review of that brick, point 1: reading the verdict off the event log
was a second opinion that could disagree with the record it described — an
accepted coverage followed by `slice_needs_person` still read as covered. The
slicer's own record decides now, against the sources and the backlog as they
stand.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(HERE / "lib"))
sys.path.append(str(HERE.parent / "slicer"))

import where
from backlog import Backlog
from finishing import ENDED_WITH_GAPS
from keep import Keeper
from slice_outcome import record_outcome
from slicer_state import close  # type: ignore[import-not-found]
from workspace import Workspace

_spec = importlib.util.spec_from_file_location("graph_goal", HERE / "graph-goal.py")
assert _spec is not None and _spec.loader is not None
graph_goal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(graph_goal)

EXPECTED_TESTS = 3
SOURCE = "README.md"          # a real file of the loop's own checkout, read only for its bytes


def campaign() -> tuple[Workspace, pathlib.Path]:
    """An approved campaign whose backlog is an empty tree, with one source
    declared. Returns the workspace and the backlog directory."""
    root = pathlib.Path(tempfile.mkdtemp())
    backlog = root / "tree"
    backlog.mkdir()
    space = Workspace(root / "campaign").init(goal="the backlog", backlog=str(backlog))
    (space.root / "approved").write_text("approved\n", "utf-8")
    space.event("sources_declared", sources=[SOURCE])
    return space, backlog


def run(space: Workspace, backlog: pathlib.Path, said: str, rc: int) -> int:
    """The plan phase's answer already on the record, then `command_run` for
    real, with nothing that would reach the repository.

    `turn_opens` is NOT patched. It used to be, by a stub that sliced the source
    gap at the top of the turn — the pre-split driver — and that is why the
    phase split could break `run` with this suite green: the fresh review's
    finding 3. The slicer has one caller now (`plan_phase.plan`), it runs before
    the driver, and `record_outcome` is the only writer that turns its exit into
    a campaign record, so this writes it where the plan phase would."""
    space.event("plan_started")
    record_outcome(Backlog(backlog), space, "the sources", None, said, rc)
    args = types.SimpleNamespace(workspace=str(space.root), dry_run=False,
                                 lanes=3, max_tasks=0,
                                 idle_seconds=300, attempt_ceiling=12, hours_ceiling=2.0)
    with unittest.mock.patch.object(Keeper, "pending", lambda self: []), \
         unittest.mock.patch("publishing.behind", return_value=False):
        return graph_goal.command_run(args)


COVERED = ("covered: approved sources are unchanged", 0)
NEEDS_PERSON = ("needs_person: the source asks for a method no gate can observe", 2)


class UncoveredTest(unittest.TestCase):
    def test_a_source_gap_that_asked_for_a_person_ends_with_that_gap(self):
        # Codex reproduced this: coverage had been accepted once, the gap later
        # needed a person, and the record still matched the backlog — so the
        # driver said the work was done. Not zero, then; and campaign 7 showed
        # which non-zero: a 1 is "try again", and nothing in the loop will ever
        # cover a gap a person was asked for, so the driver returned 1 once a
        # minute until the supervisor called it dead. 78 is the ending that
        # records the gap and stands the supervisor down.
        space, backlog = campaign()
        repo = where.loop()
        close(backlog, [repo / SOURCE], "accepted", repo, [])

        self.assertEqual(ENDED_WITH_GAPS, run(space, backlog, *NEEDS_PERSON))

    def test_a_coverage_record_matching_the_sources_and_the_backlog_finishes(self):
        space, backlog = campaign()
        repo = where.loop()
        close(backlog, [repo / SOURCE], "accepted", repo, [])

        self.assertEqual(0, run(space, backlog, *COVERED))

    def test_a_source_edited_in_the_main_checkout_never_deletes_the_record(self):
        """The slicer judges its sources in a clean checkout of the campaign
        branch tip (slice_turn.py): the driver's own working tree is not that
        checkout. A digest taken here disagreed with the record the slicer had
        just written, deleted it, and bought a fresh planner call and coverage
        review on every restart, for ever."""
        space, backlog = campaign()
        repo = where.loop()
        close(backlog, [repo / SOURCE], "accepted", repo, [])
        dirty = pathlib.Path(tempfile.mkdtemp())
        (dirty / SOURCE).write_text((repo / SOURCE).read_text("utf-8") + "\nedited\n", "utf-8")

        with unittest.mock.patch.object(where, "repo", return_value=dirty):
            code = run(space, backlog, *COVERED)

        self.assertTrue((backlog / ".slicer-state.yaml").exists())   # never the driver's to delete
        self.assertEqual(0, code)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
