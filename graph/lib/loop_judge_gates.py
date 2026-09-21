"""Which gates the branch must pass, whose gate it was when one fails, and
what happens to the two cards when the gate turns out to be the defect.

Split out of `loop_judge` at the 200-line cap; `loop_judge` imports the names
back, so `loop_judge._gates_on_the_branch` still names this one function.
"""

from __future__ import annotations

from backlog_reach import overlap, reach
from backlog_status import is_live
from gate_baseline import same_failure
from keep_gate import GateMutatedTree
from loop_types import TaskOutcome


def _gates_on_the_branch(loop, task: dict) -> list[str]:
    """This card's gate and completed cards whose files this card affects.

    Wider integration belongs in a task whose declared gate runs that check.

    A live gate is never included — running it again would repeat a one-shot
    reset, run or kill — and a live card runs alone, so nothing moved under it.
    """
    if is_live(task):
        return []
    kept = [row for row in loop.backlog.tasks()
            if row.get("status") == "done" and not is_live(row)
            and str(row.get("gate") or "").strip()]
    kept.sort(key=lambda row: str(row.get("kept_at") or ""))     # keep order, not backlog order
    my_files = {str(path).rstrip("/") for path in (task.get("files") or [])}
    gates, seen = [], set()
    for row in kept:
        if not overlap(reach(row), my_files):
            continue
        gate = str(row["gate"]).strip()
        if gate not in seen:
            seen.add(gate); gates.append(gate)
    mine = str(task.get("gate") or "").strip()
    if mine and mine not in seen:                                # and this card's, always
        gates.append(mine)
    return gates


def _gate_owner(loop, task: dict, gate: str) -> str:
    """Whose gate failed on the combined tree — "" when it is this card's own.

    `_gates_on_the_branch` puts this card's gate in last and never repeats a
    text already in the list, so a match against another card is only reached
    when the failing gate is not this card's. An unnamed gate answers "": the
    failure is charged the way it always was.
    """
    gate = gate.strip()
    if not gate or gate == str(task.get("gate") or "").strip():
        return ""
    for row in loop.backlog.tasks():
        if str(row.get("id")) != str(task.get("id")) \
                and str(row.get("gate") or "").strip() == gate:
            return str(row.get("id"))
    return ""


def _gate_is_defective(loop, task: dict, clash) -> bool | None:
    """True for the same old failure, False for new evidence, None without proof."""
    if isinstance(clash, GateMutatedTree):
        return True
    return same_failure(loop, task, clash)


def _send_to_its_owner(loop, task: dict, tree, owner: str, clash) -> TaskOutcome:
    """ANOTHER card's gate, red on the branch tip WITHOUT this card's work — or
    one that edited the tree it judged: the gate is what needs repairing, and no
    builder of this card can do it.

    So this card pays no rebuild round — its tree is kept — and the OWNER is
    given the repair: back to `todo`, its contract read again before anything
    runs that gate (`gate_reviewed_first`), the reason on the card, and the
    rounds it spent reaching done cleared — with the gate charges behind them
    (`gate_rounds`), which a later repair would otherwise refund against rounds
    it never paid for — because repairing the gate is new work. A hold a person
    put on the owner is passed back untouched, and only a card that is still
    `done` is requeued: a card another lane is building is not this failure's
    to rewrite.

    This card then waits the way the loop already makes a card wait — the owner
    goes in its `needs` — instead of being offered again and again into the
    watchdog's quarantine. What bounds the wait is the owner's own round cap: an
    owner that spends it ends `rejected`, never settles, and a person is the
    next actor for both cards, which the doctor's starved check says out loud.

    A `done` owner is the one exception: accepted work never reopens for new
    work's sake. Reopening it would spend this card's rounds retrying into the
    same red gate for ever, since the owner would settle `done` again the
    instant the repair lands and nothing would tell the two apart. So a `done`
    owner is left exactly as it was, and this card is parked with
    `blocked_by_human` for a person to make the new decision the defect calls
    for — not offered again, and not the owner's `needs` to wait on, since a
    `done` id is already "finished" to every reader that checks `needs`.
    """
    task_id = task["id"]
    # One phrase, on the event and on the owner's card: a repair sent off with
    # the wrong reason reads the gate for a redness that was never there.
    defect = ("edited the tree it judged" if isinstance(clash, GateMutatedTree)
              else f"is red on the branch tip without {task_id}'s work")
    why = (f"{owner}'s gate {defect}: "
           f"{owner} is what gets repaired, not this card — {clash}")
    tree.keep(why[:200])
    loop.space.event("failed", task=task_id, step="combined_gate",
                     gate_owner=owner, why=why[:400])
    with loop.backlog.only_writer():
        owned = loop.backlog.task(owner) or {}
        if owned.get("status") == "done":
            loop.backlog.set_status(task_id, "todo", blocked_by_human=True,
                                    rebuild_from=tree.path, refused_why=why[:400])
        else:
            needs = list(dict.fromkeys([*(task.get("needs") or []), owner]))
            loop.backlog.set_status(task_id, "todo", rebuild_from=tree.path,
                                    needs=needs, refused_why=None)
    return TaskOutcome("rejected", why, tree.path)
