"""Running a turn's cards side by side, split from `turn.py` at the 200-line cap.

One thread per card, each with its own worktree and its own claim; the task list
has one writer at a time. `turn.run_lanes` is still the name every caller uses.
"""

from __future__ import annotations

import os
import threading

import lane_closing
import runner
import worktree
from prompts import moved_under
from workspace_claims import _now


def _tried(unrecorded: list, task_id: str, what: str, write):
    """One write of a lane's failure, on its own, and what stopped it.

    A full disk does not fail one append, it fails all of them — the report of
    the first failure included — and none of those may cost the card the writes
    that come after it."""
    try:
        write()
    except BaseException as broken:   # noqa: BLE001 — a record nobody could write is the driver's news
        unrecorded.append(f"{task_id} {what}: {broken!r}"[:300])
        return broken
    return None


def _park(book, space, task: dict, why: str) -> None:
    """The lane's own death, on the card — while the card is still the one this
    lane took.

    The same one rule every other ending reads (`contract.moved_under`), under
    the backlog lock with the write. It covers what the plain `!= "done"` check
    covered — a lane that died AFTER its keep must not undo it, or the card
    drops out of the gates every later combination is checked against — and the
    rest of it too: a drop, a hold or a rewrite decided while the lane ran, and
    an ending the loop itself wrote before the lane fell over.
    """
    with book.only_writer():
        moved = moved_under(book.task(task["id"]), task)
        if moved:
            space.event("card_moved", task=task["id"], step="lane", why=moved)
            return
        book.set_status(task["id"], "lane_failed", refused_why=why)


def run_lanes(loop, book, space, tasks: list[dict], turn_id: str = "") -> tuple:
    """Run these cards side by side, one thread each, and wait for them all.

    Each has its own worktree and its own claim; the task list has one writer at
    a time (Backlog._only_writer). A card that failed the same way twice is left
    for a person, as when the loop ran one card at a time.
    """
    states: list = []
    unrecorded: list = []
    trees = {task["id"]: [] for task in tasks}
    processes = {task["id"]: [] for task in tasks}
    stopping = threading.Event()

    def lane(task: dict) -> None:
        worktree.owned.trees = trees[task["id"]]
        runner.owned.processes = processes[task["id"]]
        runner.owned.stopping = stopping
        print(f"{_now()} " + (f"→ {task['id']}: {task['goal']}").replace("\n", f"\n{_now()} "), flush=True)
        # `claim` writes the claims file under its own lock and records the
        # `claimed` event after releasing it, so a failure in that second step
        # leaves the claim standing. The lane holds one from the moment it asks
        # for it, not from the moment the call returns — and everything from
        # here on is inside the try, so a lane that dies asking is heard too.
        holding = False
        try:
            # The claim is taken under the BACKLOG lock, which is also the lock a
            # slice answer takes to write this card (`slice_outcome`). Whichever
            # gets there first wins and the other reads the result: a claim before
            # the answer means the answer touches nothing, and an answer before the
            # claim is on the card this lane reads here, under that same lock.
            #
            # What it reads may no longer be the card this turn chose. A drop, a
            # hold, a contract rewritten — decided by a person or another writer
            # between the picking and this moment — and running it anyway finishes
            # a card somebody had settled: a dropped card came back `done`. The
            # lane takes what it was given only while that is still what stands.
            with book.only_writer():
                fresh = book.task(task["id"])
                gone = moved_under(fresh, task)   # one rule: hold, contract, status, needs
                if not gone:
                    task = fresh
                    holding = True
                    space.claim(task["id"], pid=os.getpid(), pgid=os.getpgid(0),
                                account="lane", worktree="")
            if gone:
                # Nothing was claimed, so nothing is released: the card belongs
                # to whoever decided it, and this lane leaves it alone.
                print(f"{_now()} " + (f"  {task['id']} was decided while the turn started: {gone[:160]}").replace("\n", f"\n{_now()} "), flush=True)
                space.event("lane_skipped", task=task["id"], why=gone[:300])
                return
            out = loop.run_task(task)
        except BaseException as error:   # noqa: BLE001 — a lane that dies must be heard
            # A swallowed thread exception left the driver reporting a turn that
            # never happened: the task is parked and a person is told. Each of
            # those writes stands alone, because the thing that killed the lane
            # is often the thing that stops it being written down.
            why = f"the lane raised: {error!r}"[:400]
            _tried(unrecorded, task["id"], "the failure",
                   lambda: space.event("failed", task=task["id"], step="lane", why=why))
            _tried(unrecorded, task["id"], "the alert", lambda: space.alert(task["id"], why))
            # A lane that never held the card writes no status: the drop or hold
            # it just read is somebody else's decision to keep.
            if holding:
                _tried(unrecorded, task["id"], "parking the card",
                       lambda: _park(book, space, task, why))
            states.append("failed")
            return
        finally:
            if holding:
                stuck = _tried(unrecorded, task["id"], "releasing the claim",
                               lambda: space.release(task["id"]))
                # `release` writes the claims file first and events after, so a
                # failure does not mean the claim is still there. Ask the file.
                if stuck and task["id"] in space.claimed_now():
                    # A claim left behind blocks the task for ever: a person hears it too.
                    _tried(unrecorded, task["id"], "the alert about that claim",
                           lambda: space.alert(
                               task["id"], f"the lane could not release its claim: {stuck!r}"[:300]))
        states.append(out.state)
        print(f"{_now()} " + (f"  {task['id']} {out.state}: {out.why[:200]}").replace("\n", f"\n{_now()} "), flush=True)
        if out.state == "failed" and space.needs_slice(task["id"]):
            print(f"{_now()} " + (f"  {task['id']} failed twice the same way — it needs re-slicing").replace("\n", f"\n{_now()} "), flush=True)
            book.set_status(task["id"], "needs_slice")

    threads = []
    space.turn_id = turn_id
    try:
        for task in tasks:
            why = lane_closing.capacity(getattr(loop, "repo", os.getcwd()))
            if why:
                space.event("waiting", task=task["id"], why=why)
                states.append("waiting")
                break
            thread = threading.Thread(target=lane, args=(task,), name=task["id"])
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
    except BaseException:
        stopping.set()
        lane_closing.interrupt(processes)
        raise
    finally:
        try:
            for thread in threads:
                thread.join()
            unrecorded.extend(lane_closing.close(trees, processes, book, space))
        finally:
            space.turn_id = ""
    if unrecorded:
        # Every lane has released what it held and parked what it could, and
        # what is left is a record with holes in it. The log is the product: a
        # turn nobody could write down is not a turn to build the next one on,
        # so the driver hears it here, in its own frame, rather than in a
        # traceback printed by a thread nobody reads.
        raise RuntimeError("the campaign record could not be written — " + "; ".join(unrecorded[:3]))
    # "the fault is outside the task" only when EVERY lane says so: one lane hitting
    # a usage limit is not a reason to pause the others' progress.
    outside = bool(states) and all(state in ("waiting", "harness") for state in states)
    return len(threads), outside
