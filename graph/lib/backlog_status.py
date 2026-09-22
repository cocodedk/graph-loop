"""What a task's status means, and what a slice keeps from its parent.

Split from `backlog` at the 200-line cap. The file reading and the writing
stay there; this is the vocabulary three parts of the loop must agree on — the
picker, the doctor's starvation check and the board — because when they
disagreed the board reported a starved queue that was not one.
"""

from __future__ import annotations

RUNNABLE = "todo"
# How many times a card may go back to its builder. The rejection path and the
# timeout path both count to it, but a card can be left `todo` with its round
# already spent — a review that never happened, a replan — and the picker
# offered it anyway. The cap is read where the card is OFFERED, so no path can
# buy a fourth round by leaving the status alone.
#
# STILL THREE, and the decision to make it one is not this number alone. The owner
# decided on 18 September that a card parks on its FIRST failure and the next
# plan phase slices it. This counter cannot express that, because two paths
# increment it: the work failing (`loop_judge_retry._send_back`) and the machine
# failing (`back_in_place` — a timeout, a usage limit, a review that died). Set
# to one, a usage limit part way through rejects the card and throws its paid
# work away, which is the opposite of what that decision means. Saying it needs
# two counters, one per path, and 23 tests state the single-counter behaviour.
REBUILD_ROUNDS = 3
DONE = ("done",)
DROPPED = ("dropped",)
# What a slice keeps from its parent unless the piece says otherwise: each of
# these is a statement about how the card is judged, not about its work.
INHERITED = ("gate_files_are_the_work", "gate_has_side_effects", "helper_verbs")
"""What a slice keeps: how the card is JUDGED, and nothing else.

`blocked_by_human` is a decision about the parent at a moment, and inheriting it
stranded every piece the moment a slice was made. `expect_red` names the phrase
the PARENT's gate prints, and a piece has its own gate, so carrying it forward
refuses the piece for being red in its own way."""


def is_live(task: dict) -> bool:
    """Whether this card's gate performs the work it measures, on the one
    shared stack, rather than only checking it. DECLARED on the card by
    `gate_has_side_effects` — never inferred from an empty `files` list, the
    one place that used to guess and got it wrong for an evidence card with
    no files to change. Every reader shares this predicate so the rule has
    one home instead of drifting across a dozen re-readings of the field.
    """
    return bool(task.get("gate_has_side_effects"))


def runs_alone(task: dict) -> bool:
    """Whether this card runs by itself instead of in a parallel lane — a live
    card, because it acts on the one shared stack, OR a no-files evidence
    card, for a scheduling reason: with no files there is no edit for a lane
    to build, so the driver runs its gate on its own, one at a time. The
    no-files half is structural, not declared.
    """
    return is_live(task) or not task.get("files")


def spent_its_rounds(row: dict) -> bool:
    """Whether this card has used every round its builder gets. Read by the
    picker, which will not offer it, and by the doctor, which says so — or a
    card the loop cannot start is a queue that looks healthy and does nothing.
    """
    return int(row.get("rebuild_round") or 0) >= REBUILD_ROUNDS


def settled(rows: list[dict]) -> set:
    """Every id a `needs` may safely name as finished.

    A card that is done is finished. A card that was SLICED is finished when
    every piece it was cut into is — its work now lives in them, and waiting for
    the parent itself would wait for ever: `slice_task` never sets a parent to
    done. Two cards sat behind a sliced parent all night for exactly that.

    A dropped card settles too: it was decided against, and a card that merely
    followed it must not inherit a wait that will never end.

    A card's pieces are the union of what its own `needs` names and the cards
    that name it in `sliced_from`. A piece cut by hand sits in its own folder and
    names its parent; the parent's `needs` never lists it. Neither source stands
    in for the other, so each one alone can keep the parent open.
    """
    by_id = {row.get("id"): row for row in rows}
    cut_from: dict = {}
    for row in rows:
        parent = row.get("sliced_from")
        if parent and row.get("id"):
            cut_from.setdefault(parent, []).append(row["id"])
    settled = {row["id"] for row in rows if row.get("status") in DONE + DROPPED}
    growing = True
    while growing:            # a slice of a slice settles once its own pieces do
        growing = False
        for row in rows:
            if row.get("id") in settled or row.get("status") != "sliced" or not row.get("id"):
                continue
            pieces = list(row.get("needs") or []) + cut_from.get(row["id"], [])
            # Every piece must EXIST and be settled. Dropping the ones the
            # backlog does not hold would settle a parent on pieces nobody
            # wrote, and release everything waiting behind it.
            if pieces and all(piece in by_id and piece in settled for piece in pieces):
                settled.add(row["id"]); growing = True
    return settled
# Scheduling only: a card with no files has no edit for a lane to build, so the
# driver runs it by itself; whether its gate acts on the stack is `is_live`'s
# question, declared on the card.
EVIDENCE = "evidence"
CODE = "code"

def is_wall(row: dict) -> bool:
    """The ONE definition of a stuck CODE card the slicer may take — read by
    the turn-top hook and by slicer_law.assert_wall alike (SLICER.md: one
    shared predicate, one home). Structural conditions come first. Every
    sliceable wall requires a recorded `triage` verdict; no verdict means no
    slicing."""
    if not row.get("files") or is_live(row) or row.get("helper_verbs"):
        return False
    if row.get("blocked_by_human"):
        return False
    # Only a recorded triage verdict about the work or its contract is
    # task-shape evidence: a mute gate can park a card as needs_slice (T25,
    # twice), and B4 caps harness faults as `rejected` too — slicing a harness
    # victim rewrites an innocent card. Wall-slicing runs only on a recorded
    # verdict; the source-gap path runs regardless.
    verdict = row.get("triage")
    if verdict not in (None, "work", "contract"):
        return False                     # any other verdict routes elsewhere
    status = row.get("status")
    if status in ("green_already", "unprovable"):
        # Red-first writes these two (loop_evidence), and red-first is what
        # TRIAGE names `contract` (triage_signatures): the card's own gate is
        # the objection. No replan path reads these statuses — it takes
        # `refused_contract` alone — so the slicer is their FIRST actor
        # rather than the end of a ladder, and without this line a
        # green_already card with a contract verdict had no next actor at all.
        return verdict in ("work", "contract")
    if status in ("needs_slice", "out_of_scope", "quarantined"):
        # `out_of_scope`: the builder or the gate wrote outside the card's
        # files. Cutting it smaller is the answer only when the card really
        # does reach further than it was cut, and the fence cannot see that —
        # so `triage_signatures` leaves the scope row `unknown` and a `work`
        # verdict here is the model's reading of the paths, not the refusal
        # itself. Nothing retries an out_of_scope card, so there are no rounds
        # to spend first.
        return verdict == "work"
    if status == "rejected":
        # never before the rebuild rounds are spent: the loop retries first
        return verdict == "work" and spent_its_rounds(row)
    from replan_budget import stop_reason
    # A contract still wrong after its replans is the slicer's — but only once a
    # judge has SAID so. Without that verdict the slicer was handed two cards
    # whose blocker was a decision and a wrong contract (2026-09-01): it produced
    # no plan, and held them for hours. No verdict, no slicing.
    return (status == "refused_contract" and verdict == "contract"
            and bool(stop_reason(row)))
