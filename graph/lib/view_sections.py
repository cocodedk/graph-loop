"""The dashboard's fact sections: model calls, backlog, events, worktree,
accepted work, the time report and the last review. Each returns lines; `view.py`
owns the warnings and the screen."""

from __future__ import annotations

import collections
import datetime
import glob
import pathlib
import subprocess
import textwrap

import campaign_of
import where
from backlog import Backlog, settled
from report import as_text, report
from workspace import Workspace

CAMPAIGN = where.campaign()
_DEFAULT_BACKLOG = where.backlog()
NEEDS_A_PERSON = ("refused_contract", "rejected", "quarantined", "needs_slice",
                  "out_of_scope", "unprovable", "green_already", "blocked_by_agent",
                  "partial_by_agent", "unclear_by_agent", "live_call_lost", "live_turn_ended",
                  "live_call_open", "lane_failed")


def _current_backlog(campaign: pathlib.Path) -> str:
    """The backlog THIS campaign was started with, read from its own init
    event through `campaign_of.backlog_of` -- one home, so a section never
    shows one campaign's board mixed with another campaign's backlog. Falls
    back to the environment's default only when there is no init event yet
    (a fresh, unstarted campaign, where `backlog_of` answers `""`)."""
    return campaign_of.backlog_of(Workspace(campaign)) or str(_DEFAULT_BACKLOG)


def _events() -> list[dict]:
    return Workspace(CAMPAIGN).events()


def _local(at: str) -> str:
    """An event's own time, in the clock on the wall — the log stores UTC, and a
    person reading '14:37' beside a 16:40 header thinks two hours are missing."""
    try:
        stamp = datetime.datetime.strptime(at + "+0000", "%Y-%m-%dT%H:%M:%SZ%z")
        return stamp.astimezone().strftime("%H:%M:%S")
    except ValueError:
        return at[11:19]


def _wrap(text: str, width: int, indent: str) -> list[str]:
    return [indent + line for line in textwrap.wrap(" ".join(str(text).split()), width)]


def _after(parts: list[str], flag: str) -> str:
    """The value a flag was given on the command line, or nothing."""
    return parts[parts.index(flag) + 1] if flag in parts and parts.index(flag) + 1 < len(parts) else ""


def _effort(row: str) -> str:
    """The rung the call was actually given, from its own command line."""
    parts = row.split()
    rung = _after(parts, "--effort")
    if not rung:
        for piece in parts:               # codex takes it as -c model_reasoning_effort="high"
            if piece.startswith("model_reasoning_effort="):
                rung = piece.split("=", 1)[1].strip('"')
    return f" at {rung} effort" if rung else ""


def calls_in_flight() -> list[str]:
    """One line per model call. The match anchors on the binary itself ($3),
    because a loose pattern finds the watcher's own command line."""
    out, lines = subprocess.run(["ps", "-eo", "pid,etimes,args"], capture_output=True,
                                text=True, check=False).stdout, []
    for row in out.splitlines():
        parts = row.split()
        if len(parts) < 4:
            continue
        pid, secs, binary = parts[0], parts[1], parts[2]
        # The model and effort are on the command line; printing a remembered
        # pair said "codex at max" for years of ticks, and max is banned.
        if binary.endswith("/codex") and parts[3] == "exec":
            lines.append(f"  reviewer   {_after(parts, '--model') or 'codex'}"
                         f"{_effort(row)}, thinking {secs}s (pid {pid})")
        if (binary == "claude" or binary.endswith("/claude")) and \
                parts[3] == "--permission-mode" and parts[4:5] == ["default"]:
            # A planner is a claude call with no tools; a reviewer is one denied
            # everything that writes. Calling all three "builder" told the reader
            # a build was running when nothing was being built.
            job = ("planner" if "--tools" in parts and _after(parts, "--tools") == ""
                   else "reviewer" if "Read,Grep,Glob" in row else "builder")
            lines.append(f"  {job:<10} {_after(parts, '--model') or 'claude'}"
                         f"{_effort(row)}, working {secs}s (pid {pid})")
    return lines or ["  none — the loop is between calls, waiting, or running a gate"]


def backlog() -> list[str]:
    # Atomic snapshot: writers rename a complete file into place.
    rows = Backlog(_current_backlog(CAMPAIGN)).read()["tasks"]
    tally = collections.Counter(row.get("status", "?") for row in rows)
    lines = ["  " + "   ".join(f"{name}: {count}" for name, count in sorted(tally.items()))]
    done = settled(rows)      # one answer for what a need may name, shared with the picker
    stuck = [row for row in rows if row.get("status") in NEEDS_A_PERSON]
    if stuck:
        lines.append("  no lane will take these; the next plan phase does:")
        for row in stuck[:6]:
            lines.append(f"    {row['id']}  ({row['status']})")
            lines += _wrap(row.get("refused_why") or "", 84, "        ")[:3]
    ready = [row["id"] for row in rows if row.get("status") == "todo"
             and set(row.get("needs") or []) <= done and not row.get("blocked_by_human")]
    lines.append(f"  ready to start: {', '.join(ready[:8]) or 'nothing'}")
    held = [row["id"] for row in rows if row.get("blocked_by_human")]
    if held:
        # The hold stays on the card as stored evidence; it is not an actor.
        lines.append(f"  held on the card: {', '.join(held)}")
    return lines


# Bookkeeping the loop writes for itself: a person reads what happened, not
# that a prompt was saved to disk.
BOOKKEEPING = ("artifact", "attempt", "released", "idle", "driver_started")


def last_events(count: int = 8) -> list[str]:
    lines = []
    told = [row for row in _events() if row.get("kind") not in BOOKKEEPING]
    for row in told[-count:]:
        said = row.get("why") or row.get("verdict") or row.get("step") or row.get("name") or ""
        head = f"  {_local(row['at'])}  {row['kind']:<12} {row.get('task', ''):<16} "
        wrapped = _wrap(said, 80, " " * len(head))[:3] or [""]
        lines.append(head + wrapped[0].strip())
        lines += wrapped[1:]
    return lines


def live_worktree() -> list[str]:
    # The claims file is the truth about "now": it self-clears when a claimant's
    # process dies, while the event log keeps claims from drivers long gone.
    claimed = Workspace(CAMPAIGN).running()
    if not claimed:
        return ["  nothing claimed right now"]
    lines = []
    for task in sorted(claimed):        # every lane, not only the last one claimed
        tree = claimed[task].get("worktree") or ""
        if not (tree and pathlib.Path(tree, ".git").exists()):
            lines.append(f"  {task}: no worktree yet (still being reviewed)")
            continue
        status = subprocess.run(["git", "-C", tree, "status", "--short"],
                                capture_output=True, text=True, check=False).stdout.strip()
        lines.append(f"  {task}  in {tree}")
        lines += [f"    {line}" for line in (status.splitlines() or ["nothing changed yet"])[:6]]
        stat = subprocess.run(["git", "-C", tree, "diff", "--stat"], capture_output=True,
                              text=True, check=False).stdout.strip().splitlines()
        if stat:
            lines.append(f"    {stat[-1].strip()}")
    return lines


def accepted() -> list[str]:
    # Only what the campaign itself accepted -- its own `accepted` events,
    # never git log: a hand commit headed by a card id (e.g. "T26.live: …")
    # used to count as accepted work no card-write ever recorded, and a real
    # acceptance with a differently-shaped subject went uncounted.
    rows = [row for row in Workspace(CAMPAIGN).events() if row.get("kind") == "accepted"]
    if not rows:
        return ["  nothing accepted yet"]
    lines = []
    for row in rows[-6:]:
        commit = (row.get("commit") or "")[:8] or "(no commit)"
        lines.append(f"  {commit}  {row.get('task', '')}")
    return lines


def time_report() -> list[str]:
    return [f"  {line}" for line in as_text(report(Workspace(CAMPAIGN))).splitlines()]


def last_review() -> list[str]:
    answers = sorted(glob.glob(f"{CAMPAIGN}/calls/*/*-contract-answer.txt")
                     + glob.glob(f"{CAMPAIGN}/calls/*/*-diff-review-answer.txt"),
                     key=lambda path: pathlib.Path(path).stat().st_mtime)
    if not answers:
        return []
    text = pathlib.Path(answers[-1]).read_text("utf-8")
    return [f"  {answers[-1]}"] + _wrap(text, 92, "    ")[:20]
