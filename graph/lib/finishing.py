"""What it takes for a campaign to be finished. Split from `slice_turn` at the
200-line cap.

An empty backlog is not an answer on its own: a campaign with approved sources
is finished when the slicer's coverage of them has been accepted and still
holds. The slicer owns that record (`.slicer-state.yaml`, beside the backlog),
so this asks it rather than keeping a second opinion in the event log — the log
said "covered" while the same campaign was waiting for a person.
"""

from __future__ import annotations

import pathlib
import sys

# Appended, never inserted: the graph's own lib keeps first claim on every name.
sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "slicer"))
from slicer_state import accepted  # type: ignore[import-not-found]

SOURCE_GAP = "the sources"    # the label `slice_turn` gives a source-gap slice
ENDED_WITH_GAPS = 78          # the driver's deliberate ending; the supervisor stops on it


def declared_sources(space) -> list[str]:
    """The approved sources this campaign last declared — a CAMPAIGN RECORD,
    never ambient environment: the `init` event, or a later `sources` command.
    Empty when none were ever declared, and the backlog is then the whole job."""
    declared = [event["sources"] for event in space.events()
                if event.get("kind") == "sources_declared"
                and isinstance(event.get("sources"), list)
                and all(isinstance(name, str) for name in event["sources"]) and event["sources"]]
    return declared[-1] if declared else []


PLANNING_OPENS = ("plan_started", "sources_declared")


def covered_since_planning(space) -> bool:
    """Whether the planner's LAST word on the source gap was that the approved
    sources are fully covered, in the planning that is current.

    A standing record is not proof that it was judged this time, and "this time"
    is the PLAN PHASE: since the phase split, `slice_pending` has exactly one
    caller (`plan_phase.plan`) and a driver never slices at all. It used to read
    `driver_started` for that boundary, which the split made unreachable — the
    plan phase always runs before the driver, so no slice could ever follow it
    and `run` could not exit 0 for any campaign that declared sources.

    What opens a fresh window is the planning itself (`plan_started`) or a person
    redeclaring the sources, because a slice that succeeded was about the ones
    before. What closes it is the last thing the gap said: `slicer.py` validates
    its approved sources before it ever reads its record, so a source deleted
    since makes it exit 2 with the record untouched, and a gap that later asked
    for a person leaves nothing proved.

    Any `slice*` event about the gap is read, not a named few: a source-gap
    outcome this does not recognise must clear the proof rather than keep it.
    `record_outcome`'s own artifact and step records are not `slice*` kinds. And
    `covered` and nothing else: a gap slice that PUBLISHED a molecule also
    finishes cleanly, and that is the planner finding a gap, not closing it.
    """
    covered = False
    for event in space.events():
        kind = str(event.get("kind") or "")
        if kind in PLANNING_OPENS:
            covered = False
        elif kind.startswith("slice") and event.get("task") == SOURCE_GAP:
            covered = (kind == "slice_finished" and event.get("rc") == 0
                       and event.get("state") == "covered")
    return covered


def stand_down(space, book) -> int:
    """The driver's exit when nothing is startable and nothing is unfinished.

    Zero tells `supervisor.sh` the backlog is worked out and it stands down for
    good, so zero is said only when an accepted coverage still stands for the
    backlog as it is now. `ENDED_WITH_GAPS` (78) is the other deliberate
    ending: the source gap was decided against or stopped for a person, so what
    the sources still owe is recorded rather than claimed (`source_gap`). The
    supervisor stops on it too, but it is not coverage and never says it is. A
    stopped gap that ends in a 1 instead is the campaign restarting for ever
    over a question only a person can answer (campaign 7).

    A campaign whose planning failed has an empty backlog because nothing was
    planned, not because the work is done, and standing down on that is a silent
    false finish. Non-zero instead: the supervisor starts another driver, which
    puts the source gap to the slicer again.

    Whether the SOURCES are still the reviewed ones is the slicer's judgement,
    not this one's: it hashes them in the clean checkout of the campaign branch
    it plans against, and the plan phase before this driver made that judgement.
    Reading them here, from a working tree with somebody's uncommitted edit in
    it, disagreed with a record that was right.
    """
    # Asked BEFORE coverage: a campaign whose source gap was decided against
    # will never prove coverage, and asking the other way round is the loop
    # restarting for ever over work a decision already ended.
    # `source_gap` reads this module, so its readers are imported here, not above.
    from source_gap import end_on_stopped_gap, end_on_unproved_work, ended
    gaps = ended(space)
    if gaps:
        return _ended_with(gaps)
    if declared_sources(space):
        if not covered_since_planning(space):
            gaps = end_on_stopped_gap(space, book)
            if gaps is None:
                print("not finished: the plan phase has not closed the source gap")
                return 1
            return _ended_with(gaps)
        if not accepted(book.path, book.tasks()):
            print("not finished: no accepted coverage stands for the backlog as it is")
            return 1
    # Everything else says the campaign is finished — and work the loop never
    # proved, dropped or still owed, takes the place of that zero and only of
    # that zero. A 1 above is not an ending: the supervisor starts another
    # driver and the slicer, which is shown the dropped cards' contracts, plans
    # the gap again (astra's round-3 finding 20, round-4 finding 12).
    gaps = end_on_unproved_work(space, book)
    return _ended_with(gaps) if gaps else 0


def _ended_with(gaps: dict) -> int:
    print(f"ended with gaps: {gaps['gaps'] or gaps['why']}")
    return ENDED_WITH_GAPS
