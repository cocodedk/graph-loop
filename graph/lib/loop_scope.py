"""What refuses a card before anything is paid for.

Split from `loop` at the 200-line cap. The question here is whether the builder
may edit the test that judges its own work.
"""

from __future__ import annotations

import pathlib


def gate_files(task: dict) -> list[str]:
    """The files this task's gate runs, which its builder may never edit.

    A gate whose test file is in the builder's hands proves nothing: the test
    can be gutted until it passes. The reviewer refused three tasks for exactly
    this before the loop checked it itself.
    """
    gate = str(task.get("gate") or "")
    judges = []
    for path in task.get("files") or []:
        name = pathlib.Path(str(path))
        is_test = name.name.startswith("test_") or "tests/" in str(path)
        if is_test and name.stem in gate:
            judges.append(str(path))
    return judges
