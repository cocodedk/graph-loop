"""Close only checkouts and children registered by this driver's lanes."""

from __future__ import annotations

import shutil
import tempfile

from machine_read import meminfo

MEMORY_FLOOR_KB = 512 * 1024
DISK_FLOOR_BYTES = 1024 ** 3


def capacity(repo: str) -> str:
    """One admission reading before a lane opens; doubt means wait."""
    try:
        available = meminfo().get("MemAvailable")
        if available is None or available < MEMORY_FLOOR_KB:
            return "waiting for free memory"
        for path in (repo, tempfile.gettempdir()):
            if shutil.disk_usage(path).free < DISK_FLOOR_BYTES:
                return "waiting for free disk"
    except OSError:
        return "waiting for a capacity reading"
    return ""


def close(trees: dict, processes: dict, book, space) -> list[str]:
    """The driver calls this after joining every lane, even one that crashed.

    Checkouts are private clones: deleting one deletes its private branches
    and administrative records too. Accepted commits already live on the
    campaign branch. No shared branch or historical checkout is swept.
    """
    failures = []
    for task_id, checkouts in trees.items():
        if not checkouts and not processes[task_id]:
            continue
        try:
            for child in processes[task_id]:
                if child.poll() is None:
                    child.terminate()  # the command parent closes its own descendants
                    child.wait(timeout=10)
            paths = {tree.path for tree in checkouts if tree.path}
            for tree in checkouts:
                tree.remove()
            with book.only_writer():
                card = book.task(task_id)
                if card and card.get("rebuild_from") in paths:
                    book.note(task_id, rebuild_from=None, session="", finished=None)
            space.event("lane_closed", task=task_id)
        except Exception as fault:  # noqa: BLE001 — each lane must get its closing step
            failures.append(f"{task_id} cleanup: {fault!r}"[:300])
    return failures


def interrupt(processes: dict) -> None:
    """Ask only still-unreaped direct children owned by this turn to close."""
    for children in processes.values():
        for child in children:
            if child.poll() is None:
                child.terminate()
