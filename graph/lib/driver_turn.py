"""What the driver does around its lanes: the boundary in, the reading out.

Split from `graph-goal.py` at the 200-line cap; that file keeps the command
surface and imports these back. `turn.py` holds the middle of the same turn —
what it decides before it picks work — and the driver still calls `turn_opens`
itself, because that is the one step a test stands in for.

A keep already written off is retired before reconciliation can meet its note
again, which is the one ordering in `before_turn` that is not free to move.
"""

from __future__ import annotations

from backlog_status import settled
from doctor import as_text as doctor_text
from doctor import diagnose
from publishing import reconcile, settle_superseded
from watchdog import already_said
from watchdog import check as watchdog_check


def before_turn(loop, book, space, args) -> None:
    """The two steps of the driver's boundary, in that order.

    A dry run passes through: it is not the driver, and must not write — not
    even to close out a card-write somebody else lost.
    """
    if args.dry_run:
        return
    settle_superseded(space)
    reconcile(loop, book, space)


def after_lanes(book, space, args, taking: list[dict]) -> None:
    """What the loop asks itself once its lanes have finished.

    Nobody is here to notice the mistakes we have made before, so the loop asks
    the doctor and reads its own log — the same ending twice, several turns with
    nothing finished, hours or answered attempts run on since progress — and
    writes the answer into that log rather than waiting to be asked.
    """
    complaints = diagnose(book, space)
    if complaints:
        print(doctor_text(complaints))
        space.event("doctor", complaints=[f"{one.about}: {one.what}" for one in complaints])
    verdict = watchdog_check(space, attempt_ceiling=args.attempt_ceiling,
                             hours_ceiling=args.hours_ceiling)
    if verdict.futile and not already_said(space):
        # Say it once, where the red-flag check shows it, and carry on: time is
        # the only ceiling here, and a stopped loop at the weekend is a queue
        # for a person (the owner, 2026-08-29: never leave it stopped). Only
        # stop.flag stops the campaign.
        print(f"FUTILE: {verdict.why}")
        # The alert first: the blocked event is what `already_said` reads, so a
        # crash between the two must leave the alert, not swallow it.
        space.alert("the campaign", verdict.why)
        space.event("blocked", why=verdict.why)
    if verdict.spinning and (verdict.task or taking):
        _park(book, space, verdict, taking)
    elif verdict.stuck and not already_said(space):
        # The CAMPAIGN is not landing work — nobody's task in particular, so no
        # quarantine. Said ONCE until the next progress, like futility: the
        # count in the message grew every turn and so did the alerts.
        space.alert("the campaign", verdict.why)
        space.event("blocked", why=verdict.why)
        print(f"  note: {verdict.why[:160]}")


def _park(book, space, verdict, taking: list[dict]) -> None:
    """Quarantine the task that keeps ending the same way — never the one that
    happened to run last.

    Read and write under one lock, or a card that finishes between them is
    undone. `only_writer` is reentrant (lib/backlog.py), so `set_status`'s own
    acquire is free. `settled` is the done/dropped/sliced vocabulary `run_lanes`
    already checks for "done" (lib/lanes.py) — any of those must stay finished,
    not only a plain "done".
    """
    spinner = verdict.task or (taking[-1]["id"] if taking else "")
    with book.only_writer():
        fresh = book.tasks()
        card: dict = next((row for row in fresh if row.get("id") == spinner), {})
        # a fresh slice fails settled() until its atoms land, yet "sliced" must
        # never be overwritten either
        if spinner not in settled(fresh) and card.get("status") != "sliced":
            book.set_status(spinner, "quarantined", refused_why=verdict.why[:400])
            space.event("quarantined", task=spinner, why=verdict.why[:400])
            print(f"  quarantined {spinner}: {verdict.why[:160]}")
        else:
            # The card moved on (done/dropped/sliced) before this write landed,
            # so the quarantine is skipped — but the spin still happened. Name
            # that truthfully, or watchdog.check() (its SPIN_RESET) keeps
            # counting endings from before this turn and replays the same stale
            # spin forever.
            space.event("spin_spent", task=spinner, why=verdict.why[:400])
