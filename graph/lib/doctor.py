"""The check nobody else will run: the loop looking for the mistakes it has made before.

Every complaint here was a real defect that a person had to notice — a gate that
judged the wrong tree, a task whose builder could edit its own judge, a claim left
by a killed driver, a supervisor that quietly died. While there is nobody to
notice, the loop asks itself these questions every round and says so out loud.

A complaint is never fixed here. It is named, with the thing to do about it.
"""

from __future__ import annotations

import glob
import os
import re as _re
import time

import where
from backlog_status import is_live
from doctor_auth import check_auth
from doctor_slices import check_orphan_slices
from doctor_spend import check_costly_silence
from doctor_starved import check_starved
from doctor_types import Complaint
from doctor_words import operand_spans
from gate_shell import has_pipefail_header
from loop_scope import gate_files
from worktree import stack_lock

REPO = str(where.repo())


def _tasks(backlog) -> list[dict]:
    try:
        return backlog.tasks()
    except (OSError, ValueError, KeyError):   # a half-written backlog is a fault too
        return []


# Absolute paths a gate may legitimately name: the system, not a checkout.
# Matching only THIS process's repository missed a gate naming a different
# checkout — and made the test pass by accident wherever it happened to run.
SYSTEM_PATHS = ("/usr/", "/bin/", "/sbin/", "/lib/", "/etc/", "/dev/", "/proc/", "/opt/")


def _names_a_checkout(gate: str) -> bool:
    """Whether this gate reaches out of its own worktree by absolute path.

    A path starts at a real boundary and continues with a path character, so an
    awk or sed pattern (`/^OK/`, `/\\1/p`) and a URL (`http://host/health`) are
    not paths, while `X=/srv/repo/x` is one. A file the gate itself CREATES — by
    redirect or by `tee` — is its own scratch and judges nothing; every other absolute path
    reaches into some checkout, whichever one this process happens to be in.

    A route quoted as a grep, sed or awk operand has the same two-segment
    shape as a checkout path, so `operand_spans` blanks it before the path
    search runs; `-f`/`--file` names a real file, so it is left alone.
    """
    scratch = set(_re.findall(r">>?\s*(/[^\s;:'\"()]*)", gate))
    scratch |= set(_re.findall(r"\btee\s+(?:-a\s+)?(/[^\s;:'\"()]*)", gate))
    scrubbed = gate
    for start, end in operand_spans(gate):
        scrubbed = scrubbed[:start] + " " * (end - start) + scrubbed[end:]
    for found in _re.findall(r"(?<![\w./:-])/[A-Za-z0-9_.][^\s;:'\"()]*", scrubbed):
        if found.startswith(SYSTEM_PATHS) or found in scratch:
            continue
        # A checkout path has two real segments at least: `/s/` is a sed
        # fragment, `/srv/other-checkout` is somebody's tree.
        parts = [piece for piece in found.rstrip("/").split("/") if piece]
        if len(parts) < 2:
            continue
        return True
    return False


def _is_multi_step(gate: str) -> bool:
    """Whether this gate proves more than a single check.

    An explicit `&&` chain or anything naming `run_all` says so outright.
    Otherwise, more than one non-empty, non-comment line AFTER a fail-fast
    header (`gate_shell.has_pipefail_header`) counts — the header itself
    is not a check, so `set -e -o pipefail` plus one test line is still a
    one-test gate. Without the header, an earlier failing line can still
    hide behind a later passing one, so bare newline-separated commands
    prove nothing.
    """
    if "&&" in gate or "run_all" in gate:
        return True
    if not has_pipefail_header(gate):
        return False
    lines = [line for line in gate.splitlines()
             if line.strip() and not line.strip().startswith("#")]
    return len(lines[1:]) > 1


def check_backlog(backlog) -> list[Complaint]:
    out = []
    for task in _tasks(backlog):
        gate = str(task.get("gate") or "")
        name = task.get("id", "?")
        from tools import helper
        # a LIVE gate must reach the helper by the main checkout's absolute
        # path (a worktree copy is what the guard forbids) — the helper only,
        # as a complete word: the helper's path plus a suffix, or any other absolute repository
        # path still judges the checkout and is still a fault
        home = helper()
        stripped = (_re.sub(r"(?<!\S)" + _re.escape(home) + r"(?=\s|$)", "", gate)
                    if is_live(task) and home else gate)
        if _names_a_checkout(stripped):
            out.append(Complaint(
                name, "its gate names an absolute path, so it judges some other "
                "checkout instead of the task's own worktree",
                "make every path except the live helper relative"))
        if not gate.strip() and task.get("status") == "todo":
            out.append(Complaint(name, "it has no gate, so nothing can prove it done",
                                 "give it a gate that fails today"))
        lasting = task.get("gate_when_kept")
        if task.get("gate_until_kept") is True and (not isinstance(lasting, str) or not lasting.strip()):
            out.append(Complaint(
                name, "its one-shot gate has no lasting check, so regression protection ends at keep",
                "give gate_until_kept a non-empty gate_when_kept"))
        judges = gate_files(task)
        if judges and not task.get("gate_files_are_the_work"):
            out.append(Complaint(
                name, f"its builder may edit the test that judges it ({judges[0]})",
                "take the test out of its files, or say writing it is the work"))
        done = str(task.get("done_when") or "")
        # A gate that is a committed script runs whatever that script runs: the
        # complaint is about a one-test gate written inline, not about a name.
        script = gate.strip().startswith("bash ") and gate.strip().endswith(".sh")
        if "suite" in done and not script and not _is_multi_step(gate):
            out.append(Complaint(
                name, "it claims a whole suite in `done_when` while its gate runs "
                "one test",
                "either run the suite in the gate or claim only what the gate proves"))
    return out


def check_campaign(space, rows: list[dict] | None = None,
                   claimed: dict | None = None) -> list[Complaint]:
    out = []
    if (space.root / "stop.flag").exists():
        out.append(Complaint("the campaign", "the stop flag is set, so nothing will run",
                             "remove it when the loop should carry on"))
    import datetime
    for task_id, row in (space.claimed_now() if claimed is None else claimed).items():
        since = row.get("since", "")
        try:
            held = datetime.datetime.now(datetime.timezone.utc) -                 datetime.datetime.strptime(since + "+0000", "%Y-%m-%dT%H:%M:%SZ%z")
            hours = held.total_seconds() / 3600
        except ValueError:
            hours = 0
        # A claim is healthy while its task is being reviewed and built; only one
        # held for hours points at something wedged.
        if hours >= 1.5:
            out.append(Complaint(task_id, f"it has been claimed for {hours:.1f} hours",
                                 "check what its process is doing before restarting"))
    # The lock decides whether its holder is gone; a second copy of the rule here
    # is a second rule, and this one still asked the process GROUP.
    lock = stack_lock()
    if lock.path.exists() and lock.holder_is_gone():
        out.append(Complaint("the live stack", "its lock is held by a process that "
                             "is gone", f"delete {lock.path}"))
    latest = max(glob.glob(f"{space.root}/events*.jsonl"), key=os.path.getmtime,
                 default="")
    if latest and time.time() - os.path.getmtime(latest) > 3600:
        out.append(Complaint("the campaign", "nothing has happened for over an hour",
                             "check the supervisor and the driver are running"))
    return out


def diagnose(backlog, space, rows: list[dict] | None = None) -> list[Complaint]:
    # A slice answers for its parent only when a successor names it: the
    # status alone is a hand edit, the successor is the evidence.
    tasks = _tasks(backlog)
    parents = {row.get("sliced_from") for row in tasks
               if row.get("sliced_from") and row.get("id") and row.get("sliced_from") != row.get("id")}
    sliced = {row.get("id") for row in tasks if row.get("status") == "sliced" and row.get("id") in parents}
    # One claims snapshot for every check, read without the lock: `running`
    # prunes and writes, and the board must never wait behind a keep.
    claimed = space.claimed_now()
    return (check_backlog(backlog) + check_campaign(space, rows, claimed)
            + check_costly_silence(space, sliced, rows, claimed)
            + check_starved(tasks, len(claimed)) + check_auth()
            + check_orphan_slices(tasks, parents))


def as_text(complaints: list[Complaint]) -> str:
    if not complaints:
        return "nothing to complain about: the gates, the claims and the log all look right"
    lines = [f"{len(complaints)} things worth a look:"]
    for row in complaints:
        lines.append(f"  {row.about}: {row.what}")
        lines.append(f"      → {row.do}")
    return "\n".join(lines)
