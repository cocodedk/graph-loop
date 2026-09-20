"""What a finished slicer call means for the card it targeted.

Split from `slice_turn` at the 200-line cap: that module builds the call
(target, argv, worktree, subprocess), this one reads what it answered."""

from __future__ import annotations

from prompts import moved_under

# outcomes where nobody answered: they cost no replans and never count toward
# a cap — retrying an outage is free, repeating an answered refusal is not
# `card_moved` is the same shape: a person decided while the slicer planned,
# so nobody judged whether this target plans as it now stands.
# `timeout` was here and is not: a call that ran to its 7200 s ceiling read the
# question and made its own paid planner calls, so it is a call that did not
# finish, not a resource that refused before reading — uncounted, it spent two
# hours on the same card every turn for ever (astra round 4, finding 8).
UNANSWERED = ("(unparsed)", "review_unavailable", "planner_unavailable", "card_moved")

# The slicer's own retry budget, separate from is_wall's replans precondition.
MAX_SLICES = 3


def _not_a_wall(said: str, target: dict | None) -> bool:
    """Whether `said`'s first line is EXACTLY slicer_law.assert_wall's own
    refusal for THIS target — bare (slicer.py's first guard, before any
    model call) or `validation_refused:`-prefixed (contracts.validate's,
    reached only after a repair round). Exact equality only, target id
    substituted: unrelated validation text that merely mentions the phrase,
    or the phrase about another id, is an answered refusal like any other —
    a harness race is narrower than "the words appear somewhere"."""
    if target is None:
        return False
    first_line = said.split("\n", 1)[0].strip()
    tail = f"{target['id']} is not a stuck CODE card the slicer may take"
    return first_line in (tail, f"validation_refused: {tail}")


def _moved(book, space, label: str, target: dict) -> str:
    """Why this card is no longer the one the slicer planned from, "" when it
    still is — asked right before each write it guards, under the caller's lock.

    A slice call runs for up to two hours, and a drop, a hold or a rewrite
    decided in them is newer than everything this answer was decided from: the
    same one rule every other long call's ending reads (`contract.moved_under`).
    Asked HERE and not at the top, because the answer's own `slice_finished`
    event is a window boundary two readers count from (`watchdog_spin`,
    `source_gap`) and a slice that worked moves the card itself.
    """
    moved = moved_under(book.task(target["id"]), target)
    if moved:
        space.event("card_moved", task=label, step="slice", why=moved)
    return moved


def record_outcome(book, space, label: str, target: dict | None,
                    said: str, rc: int) -> None:
    """Held for a person, an answered refusal that spends one SLICE round, a
    harness race that spends nothing, or an ordinary finish.

    Every one of those writes the card, so the claims file is asked first: a
    card a lane holds RIGHT NOW is not this answer's to hold or to charge. A
    lane that has finished has released its claim, and the card is this
    answer's again — which is why the question is asked here and not of the
    list the slicer was handed.

    The question and the writes are one hold of the BACKLOG lock, which is the
    lock a lane takes to claim (`turn.run_lanes`): a claim cannot land between
    them. Whichever gets the lock first wins — a claim before this skips every
    write, and a write before a claim is on the card the lane then reads under
    the same lock. Nothing here takes the campaign lock while holding this one
    except through `space`, which never reaches back for the backlog."""
    space.artifact(label, "slice-output", said)
    with book.only_writer():
        _decide(book, space, label, target, said, rc)


def _decide(book, space, label: str, target: dict | None, said: str, rc: int) -> None:
    """The answer's own writes, under the caller's lock (`Backlog.only_writer`
    is reentrant in one thread, so `book.note` below re-enters it)."""
    if target is not None and target["id"] in space.running():
        # A lane took the card while the slicer planned. Every card write below
        # lands on a build in flight — a person's hold, a slice round, a refusal
        # reason the builder never saw — and nobody judged this card as it now
        # stands. Uncharged and untouched, like every other race here. The
        # answer itself is kept: the artifact above is the whole of it.
        space.event("slice_skipped", task=label,
                    why=f"a lane is building {target['id']}: {said[-200:]}")
        return
    if said.startswith("needs_person:"):
        # a machine-readable outcome: a target is held once; a source-gap
        # answer alerts once and is not retried every idle turn
        why = said.split(":", 1)[1].strip()[:300] or "the slicer needs a person"
        if target is not None:
            if _moved(book, space, label, target):
                return      # somebody settled this card; the alert would reopen it
            # `needs_person`, not `loop`: this is the reviewer's own NO, and the
            # plan phase drops only what it holds itself (`drop_loop_holds`).
            # Dropped, this refusal became a gap the next slicer was asked to
            # close again — and the report records that the same question, on
            # the same tip, was answered both ways. Re-rolling a die that is
            # known to come up wrong is not a decision. Held, it ends the
            # campaign with the refusal recorded (`source_ended`), which is the
            # loop deciding to stop rather than waiting for anybody.
            book.note(target["id"], blocked_by_human=True, held_by="needs_person",
                      slices=None, refused_why=why)
        already = any(why in str(line) for line in space.alerts())
        if not already:
            space.alert(label, f"the slicer needs a person: {why}")
        space.event("slice_needs_person", task=label, why=why)
        return
    if _not_a_wall(said, target):
        # the ground moved under the slicer, not its own answer: nobody
        # judged whether this target plans, so it costs no slice and holds
        # nobody (touches nothing on the card)
        space.event("slice_skipped", task=label, why=said[-300:])
        return
    state = said.split(":", 1)[0].strip() if ":" in said.split("\n", 1)[0] else ""
    space.event("slice_finished", task=label, rc=rc,
                state=state or "(unparsed)", why=said[-300:])
    if target is not None and rc != 0 and state != "needs_person" and state not in UNANSWERED:
        if _moved(book, space, label, target):
            return          # somebody settled this card while the slicer planned
        # a refusal costs one capped SLICE round of the slicer's own; replans stays put
        slices = int(target.get("slices") or 0) + 1
        if slices >= MAX_SLICES:
            book.note(target["id"], blocked_by_human=True, held_by="loop", slices=slices,
                      refused_why=f"the slicer failed {slices} times: {said[-200:]}")
            space.alert(target["id"], f"the slicer failed {slices} times; a person decides")
        else:
            book.note(target["id"], slices=slices, refused_why=said[-300:])
