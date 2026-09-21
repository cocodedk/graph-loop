"""One leaf's own contract: its gate, its files and its names.

Split from `contracts` at the 200-line cap; `contracts` stays the front
door and calls this. What is left there asks about the ANSWER — its keys,
its molecule, the graph it would publish — while this asks about one card.
"""

from __future__ import annotations

import pathlib
import sys

from contract_paths import _inside, _strings
from gate_output import unsafe_gate_sinks

GRAPH_LIB = pathlib.Path(__file__).resolve().parents[1] / "graph" / "lib"
sys.path.insert(0, str(GRAPH_LIB))
from backlog_status import is_live  # type: ignore[import-not-found]
from gate_shell import (  # type: ignore[import-not-found]
    has_pipefail_header,
    pins_a_count,
)


def _task(task: dict, repo: pathlib.Path, known: set[str]) -> None:
    for key in ("goal", "gate", "done_when"):
        if not isinstance(task.get(key), str) or not task[key].strip():
            raise ValueError(f"{key} must be a non-empty string")
    sinks = unsafe_gate_sinks(task["gate"])
    if sinks:
        # Name the reason, not just the rule. A gate whose target is a variable
        # is refused because THAT variable is not a scratch directory this gate
        # made, and a message that only restates "use $(mktemp)" cannot drive a
        # repair when the gate believes it already does (2026-09-18).
        why = (f" — {sinks[0].strip(chr(34) + chr(39))} was not assigned from `mktemp` "
               "in this gate" if "$" in sinks[0] else "")
        raise ValueError(
            f"the gate writes {sinks[0]}, which nothing owns{why}: a gate's output goes to "
            "`$(mktemp)` or `$TMPDIR/...`, the home the driver removes when the gate ends")
    if str(repo) in task["gate"]:
        # The prompt used to hand the planner this path as "Repository:", and one
        # card in eight of run 6 opened its gate with `cd` to it. It is the
        # slicer's own throwaway worktree (`clean_tree.PREFIX`), deleted before
        # any builder runs, so the gate judged nothing — and the card carried a
        # machine path into a tracked note. The graph loop's doctor catches it a
        # repair round later; this is the round.
        raise ValueError(
            "the gate names the directory you are running in, which is a throwaway "
            "copy deleted before any builder starts: write every path relative, and "
            "no `cd` — the gate already runs at the root of the builder's worktree")
    if not has_pipefail_header(task["gate"]):
        raise ValueError(
            "the gate does not start with `set -e -o pipefail`: a later "
            "step can pass while an earlier one failed")
    pinned = pins_a_count(task["gate"])
    if pinned:
        raise ValueError(
            f"the gate pins EXPECTED to {pinned}: the runner's EXPECTED counts "
            "test cases and moves as tests land — assert it only against what "
            "the runner collects (`countTestCases()`/`run_all.EXPECTED`)")
    files = _strings(task.get("files"), "files")
    if not files:
        raise ValueError("the standalone slicer creates CODE atoms only")
    for raw in files:
        if ":" in raw:
            # `uses` and `creates` are names, `files` is write authority, and
            # the builder's fence compares a bare path against it. A grant of
            # `path:text` cannot match the file the card exists to write, so the
            # one file it is for is the one the fence forbids — nine of nine
            # cards in the third campaign (2026-09-18). `_inside` had no opinion
            # on it: a colon is legal in a POSIX filename.
            raise ValueError(
                f"files holds the name {raw!r}: a file grant is a path on its own, "
                f"so write {raw.split(':', 1)[0]!r}. A `path:text` name belongs in "
                "uses or creates, where it says what must be in the file")
        _inside(repo, raw, "file")
    from loop_scope import gate_files  # type: ignore[import-not-found]
    judges = gate_files(task)
    if judges and task.get("gate_files_are_the_work") is not True:
        raise ValueError(
            f"its builder may edit the test that judges it ({judges[0]}) — say "
            "writing it is the work with gate_files_are_the_work: true, or take "
            "the test out of files")
    for key in ("needs", "uses", "creates", "helper_verbs"):
        values = _strings(task.get(key, []), key)
        if key == "needs" and set(values) - known:
            raise ValueError("an atom needs a task that does not exist")
    for key in ("gate_files_are_the_work", "gate_has_side_effects", "may_add_files", "gate_until_kept"):
        if key in task and not isinstance(task[key], bool):
            raise ValueError(f"{key} must be true or false, not text")
    for key in ("note", "expect_red", "gate_when_kept"):
        if key in task and not isinstance(task[key], str):
            raise ValueError(f"{key} must be text")
    if task.get("helper_verbs"):
        raise ValueError("the standalone slicer cannot author live helper verbs")
    if is_live(task):
        raise ValueError("the standalone slicer cannot author LIVE authority")
