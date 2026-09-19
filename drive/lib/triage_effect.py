"""What one repair writes on one card, and who writes it.

Split from `triage_repairs` at the 200-line cap; that file stays the door.

A repair reads a card through `facing`'s projection and nothing else, so the
fields an approval has to bind cannot drift from the fields the repair reads:
they are the same tuple, and what is outside it is not there to be read.
"""

from __future__ import annotations

from backlog_status import REBUILD_ROUNDS, RUNNABLE, is_wall

# Every field a repair reads on a card it may touch. `triage_repairs.facing`
# records exactly these, `repair_effect` is handed exactly these, and an
# approval compares them as one dict against one dict.
READS = ("gate", "status", "blocked_by_human", "triage", "files",
         "gate_has_side_effects", "helper_verbs", "replans",
         "rebuild_round", "gate_rounds", "gate_rounds_refunded")

# What a gate repair can answer: the endings the loop wrote when the gate ran,
# or would not run. Red-first refusals (loop_evidence), a gate that failed the
# same way twice (loop_judge), the round cap (loop_judge, loop_judge_retry,
# worktree_refs) and a spin the watchdog parked (drive-goal). Every other
# ending was about something a repaired gate does not touch, and its card is
# repaired where it stands.
GATE_ENDINGS = ("green_already", "unprovable", "needs_slice", "rejected", "quarantined")


def repair_effect(found: dict, fixed: str) -> dict:
    """Every field this repair writes on this card, and the one thing it can
    only say out loud (`alert`).

    The gate and the requeue are ONE effect, written in one go: they were two
    writes, so a death between them left the gate repaired, the card still
    parked and its refund lost, while the next turn read that repaired gate as
    work already done (Codex, finding 2). Recorded whole in the approval too,
    because a status and a refund nobody was shown are effects nobody approved
    (astra's round-4 finding 11).

    The repair only fires when it CHANGES the gate, so the next round is not the
    refusal the card was parked for — but a parked status is one the picker will
    never offer, so a repair that changed nothing else reached nobody.
    `rebuild_from` stays as it is; the reason it was parked for goes.

    The rounds go back too, as far as the card says the gate cost them:
    `gate_rounds` is written where a gate failure CHARGES a round and nowhere
    else (`loop_judge_retry._send_back`), so a failure that spent nothing — a
    second identical one, which parks the card instead — gives nothing back,
    and neither does a round its builder spent on a review finding the repair
    does not answer. `gate_rounds_refunded` is how many of those charges a
    repair has already answered, so a second repair never refunds them twice.
    A card still out of rounds after that spent them on something else: a
    person is told, and the card is left where it stands. Written `todo` it
    would be a card the picker never offers and the board reads as ready
    (`backlog.ready`).

    The repair gives an owner to a card that had none; it never changes who owns
    a card. The sweep repairs every open card the repair changes, not only the
    one whose ending fired it, so two cards with a gate ending are still left
    where they stand: one a person holds, because any write of `todo` clears
    `blocked_by_human` (`Backlog._apply`) and the hold is not TRIAGE's to lift,
    and a wall, which is the slicer's — requeued with its rounds spent it would
    be offered by nobody and would not be a wall any more either.
    """
    effect = {"gate": fixed, "gate_reviewed_first": True}
    if found.get("status") not in GATE_ENDINGS or found.get("blocked_by_human") \
            or is_wall(found):
        return effect
    spent = int(found.get("rebuild_round") or 0)
    refunded = int(found.get("gate_rounds_refunded") or 0)
    refund = max(0, min(spent, int(found.get("gate_rounds") or 0) - refunded))
    if spent - refund >= REBUILD_ROUNDS:
        return {**effect, "alert": "its gate is repaired, but the rounds it has spent are "
                "not the gate's: nothing will offer it until a person re-slices it or "
                "clears them"}
    return {**effect, "status": RUNNABLE, "refused_why": None,
            "rebuild_round": (spent - refund) or None,
            "gate_rounds_refunded": (refunded + refund) or None}


def write_effect(book, space, task_id: str, effect: dict) -> None:
    """Apply one effect to one card: ONE write, then what it can only say."""
    fields = {key: value for key, value in effect.items() if key != "alert"}
    status = fields.pop("status", "")
    if status:
        book.set_status(task_id, status, **fields)
    else:
        book.note(task_id, **fields)
    if effect.get("alert"):
        space.alert(task_id, effect["alert"])
