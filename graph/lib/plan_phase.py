"""The plan phase: slice until the graph stops growing, then stop.

The two phases never mix. Planning used to happen at the top of every driver
turn — `turn.turn_opens` called the slicer, so a campaign planned and built at
the same moment. Now planning runs with no builds in flight: either the
`plan` command calls this phase, or `run` does before standing down.

Exhaustion is read from the backlog, never from what a slicer call said about
itself: the phase ends on the round that changes NOTHING there. That is the same
rule as everywhere else here — take the inventory from the tree, not from the
answer. It is deliberately not "the round that adds no card": a card that cannot
be sliced adds none, and one of those used to end the phase with every other
wall unplanned.

It also clears what the build phase left nobody: the cards the LOOP itself
parked are dropped with their gap named, and the cards the harness parked
rather than their own work go back in the queue. Nothing else does either
since the decider was cut.

What a plan phase leaves behind is a graph whose cards are all reviewed, because
the contract review a card gets is the slicer's own gate (SLICER.md). The build
phase that follows writes no cards at all: a card that fails there parks, and
the next plan phase re-slices it against the code as it then stands.
"""

from __future__ import annotations

from backlog import Backlog
from backlog_status import DONE, DROPPED, RUNNABLE, is_wall
from campaign_of import backlog_of
from finishing import ENDED_WITH_GAPS, covered_since_planning
from slice_turn import slice_pending
from waves import say as say_waves
from workspace import Workspace

# Verdicts that are not about the card: the run died, the review never
# answered, the machine was wrong. TRIAGE names them, and until the decider was
# cut it was the one thing that put such a card back — so without this they park
# for ever, with nothing wrong with them. `gate` is not here: TRIAGE repairs a
# mute gate and requeues the card itself (`triage_effect.repair_effect`).
FAULTS = ("environment", "harness", "rig", "unknown")


def drop_loop_holds(book, space) -> int:
    """Drop every card the LOOP itself parked as nobody's, gap named, and say
    how many.

    Four places hold a card the loop cannot take further: the slicer's refusal
    cap, a live turn that ended badly, a live call that never started, and the
    peers a live call held. Each wrote `blocked_by_human` for a person to read,
    and the decider was the one thing that ever lifted it. With the decider cut
    they would wait for ever, so the plan phase applies the rule the repository
    already states (CLAUDE.md § Code): what cannot be decided from the
    repository is dropped with the gap named on the card.

    Dropped, not requeued: three of the four made a LIVE call, and putting one
    back would re-run work that already touched the one shared stack without
    reading what it did. A drop settles, so the cards behind it move, and the
    work comes back as a fresh card the next slicer cuts from the same goal.

    A fifth place used to be here and is deliberately not: the slicer's
    `needs_person` answer (`slice_outcome`, `held_by="needs_person"`). That is
    a reviewer reading the repository and saying NO — the loop refusing to
    invent an external format it cannot see — and the rule above is about a
    STUCK card, not about a correct refusal. Dropping it re-opened the gap and
    asked the same question again, and the same question on the same tip has
    been answered both ways. What ends such a campaign is the driver's own
    ending, with the refusal recorded (`source_ended.unfinished_work`).

    `held_by` is what tells all of these apart from a hold a PERSON put on a
    card by hand; a person's hold is not the loop's to lift either.
    """
    dropped = 0
    for row in book.tasks():
        if row.get("held_by") != "loop" or row.get("status") in DONE + DROPPED:
            continue
        book.set_status(row["id"], "dropped", held_by=None, blocked_by_human=None,
                        refused_why=row.get("refused_why") or "the loop could not take it further")
        space.event("dropped", task=row["id"],
                    why=str(row.get("refused_why") or "the loop could not take it further")[:300])
        dropped += 1
    return dropped


def requeue_faults(book, space) -> int:
    """Put back every card the harness parked, once each, and say how many.

    Once each: `requeued` stays on the card, so a second fault of the same kind
    on the same card is taken as real and parks. A plan phase that put the same
    card back every time would hide a machine that is actually broken.

    `blocked_by_human` stops it too, the same check `triage_effect.repair_effect`
    already makes before it touches a gate: a person's hold is not a fault the
    infrastructure caused, so a retry policy is not the loop's excuse to lift it.
    """
    put_back = 0
    for row in book.tasks():
        if row.get("triage") not in FAULTS or row.get("requeued"):
            continue
        if row.get("status") in (RUNNABLE,) + DONE + DROPPED:
            continue
        if row.get("blocked_by_human"):
            continue
        book.set_status(row["id"], RUNNABLE, triage=None, refused_why=None,
                        rebuild_round=None, requeued=True)
        space.event("requeued", task=row["id"],
                    why="parked by the harness, not by its own work")
        put_back += 1
    return put_back


# A campaign is planned in tens of molecules, not thousands. The ceiling is a
# runaway guard: the phase normally ends when a round adds nothing.
MAX_ROUNDS = 200


def plan(book, space, rounds: int = 0) -> int:
    """Run the slicer until it adds nothing, and say how many cards were added.

    `rounds` stops early — one round is how a person watches the first molecule
    land before letting the rest go.
    """
    ceiling = min(rounds or MAX_ROUNDS, MAX_ROUNDS)
    # This phase is what "judged this time" means for the source gap: the driver
    # does not slice any more, so the coverage the driver stands down on is the
    # coverage THIS phase proved, and a phase that starts opens a fresh window
    # over whatever an older one closed (`finishing.covered_since_planning`).
    space.event("plan_started")
    drop_loop_holds(book, space)  # a card nobody can take is not a card
    requeue_faults(book, space)   # a card nothing was wrong with is work, not planning
    added = 0
    for _ in range(ceiling):
        was, before = _state(book), {str(row.get("id")) for row in book.tasks()}
        slice_pending(book, space)
        grew = {str(row.get("id")) for row in book.tasks()} - before
        if grew:
            added += len(grew)
            space.event("planned", task="the plan", added=sorted(grew))
        elif _state(book) == was:
            break
    return added


def _state(book) -> str:
    """The whole backlog, as one comparable string.

    Not the id set. A round that slices a card and is refused adds nothing and
    writes the attempt on the card, and reading only ids called that exhaustion:
    one card whose gate could not pass inside its own file grant ended the phase
    for the entire campaign, with every wall behind it unplanned and the source
    gap never reached. A failed attempt spends one of the card's three; after
    the third it is held and the next wall becomes the target, so the phase has
    to keep going to get there.
    """
    import json
    return json.dumps([sorted(row.items(), key=str) for row in book.tasks()],
                      default=str, sort_keys=True)


def finished(book, space) -> tuple[bool, str]:
    """Whether the graph is planned out, and what is missing when it is not.

    A finished graph and a refused round both add no card, so the phase used to
    report both as success: two campaigns ended `the plan added 8 cards`, exit
    0, on graphs whose own branch names said what had never been planned. The
    answer is not the count — it is whether the PLANNER ever said there was no
    gap left, which it records as a gap slice that finished cleanly.
    """
    # The same record the driver stands down on, read by the same function: two
    # readings of one record are two opinions, and the fresh review found them
    # disagreeing — this said finished while `run` said the gap was never sliced.
    walls = [str(row.get("id")) for row in book.tasks() if is_wall(row)]
    if not covered_since_planning(space):
        return False, ("the source gap was never closed: no round of this phase got the "
                       "planner to answer that the approved sources are fully covered")
    if walls:
        return False, f"{len(walls)} card(s) are still stuck and unsliced: {', '.join(walls[:5])}"
    return True, ""


def command_plan(args) -> int:
    """`graph-goal.py plan`: the whole plan phase, with the driver stopped."""
    import where
    space = Workspace(args.workspace or where.campaign())
    if not (space.root / "approved").exists():
        raise SystemExit("not approved — run `graph-goal.py approve` first")
    space.only_driver()          # planning and building never overlap on one campaign
    where.repo(space)
    book = Backlog(backlog_of(space))
    added = plan(book, space, rounds=args.rounds)
    print(f"the plan added {added} card{'' if added == 1 else 's'}")
    say_waves(book.tasks())     # the graph this phase leaves, as of this moment
    if args.rounds:
        return 0                     # stopped early on purpose; nothing is claimed
    done, why = finished(book, space)
    if done:
        return 0
    print(f"the plan is NOT finished: {why}")
    return ENDED_WITH_GAPS
