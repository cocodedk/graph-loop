"""One screen that says what the loop is doing. `watch.sh` is only the refresh.

Each section is one function that returns lines, so a reader — human or model —
can see the whole structure in the section list at the bottom. Everything is read
from the campaign's own files and from `ps`; the one thing remembered between calls
is when each red flag was first seen (`view_stamps`), so a warning carries its age
and a watcher can skip what it already sent."""

from __future__ import annotations

import datetime
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import where
from view_health import (
    _driver_pid,
    _driver_start,
    _supervisor_last_word,
    base_measure,
    driver_is_working,
    driver_knows_flag,
    driver_missing,
    has_kept_commit,
    recorded_branch,
    stale_driver_line,
    supervisor_owns_driver,
    supervisor_restart_aware,
    supervisor_running,
)
from view_pulse import health, health_failures
from view_sections import (
    _current_backlog,
    accepted,
    backlog,
    calls_in_flight,
    last_events,
    last_review,
    live_worktree,
    time_report,
)
from view_stamps import stamped
from workspace import Workspace

CAMPAIGN = where.campaign()
BRANCH = where.branch()


def warnings(everything: bool = False) -> list[str]:
    """The section that says something is wrong, in words, before the detail.

    Each line is a failure that happened while the dashboard sat quiet.
    `everything` is the alarm path (`--check`): every
    complaint, where the screen renders four — a capped alarm hid the fifth for
    ever. The cut is made AFTER `stamped`, or a complaint the screen left out
    loses its first-seen time and never reaches the 15-minute email."""
    lines = []
    last_word, seconds_ago = _supervisor_last_word()
    space = Workspace(CAMPAIGN); rows = space.events()   # one snapshot
    driver_pid = _driver_pid(events=rows)   # this campaign's own, by the pid it announced
    # and this campaign's own supervisor, by the pid it recorded: a matching
    # name is another campaign's as often as ours (round-4 finding 15)
    missing = driver_missing(supervisor_running(campaign=CAMPAIGN),
                             driver_pid is not None, last_word, seconds_ago)
    if missing:
        lines.append(missing)
    base = recorded_branch(rows, BRANCH)  # could mix two campaign states in one board
    def git(argv: list[str]) -> tuple[int, str, str]:
        done = subprocess.run(["git", "-C", str(where.repo(space, persist=False)), *argv], capture_output=True,
                              text=True, check=False)
        return done.returncode, done.stdout, done.stderr
    behind = (base_measure(base, git, established=has_kept_commit(rows))
              if any(row.get("kind") == "init" for row in rows) else "")
    if behind:
        lines.append(behind)
    started = _driver_start(None, rows)
    if started is not None:
        # Every module the driver can load, read from the directory rather than
        # a list kept by hand, which omitted four files the day the loop was
        # split. The view's own files are display-only and left out, or a
        # dashboard edit cried wolf within two minutes.
        here = pathlib.Path(__file__).parent
        loaded = [path for path in here.glob("*.py") if not path.name.startswith("view")]
        loaded += [here.parent / "graph-goal.py", here.parent / "graph_commands.py"]
        newest = max(path.stat().st_mtime for path in loaded if path.exists())
        # A restart already asked for silences THIS line, never the checks below
        # it: an early return here hid an expired account behind a pending restart.
        if newest > started and not (CAMPAIGN / "restart.flag").exists():
            age = int((time.time() - started) / 60)
            knows = driver_knows_flag(rows, driver_pid)
            supervised = (supervisor_owns_driver(driver_pid)
                          and supervisor_restart_aware(last_word))
            lines.append(stale_driver_line(age, knows, str(CAMPAIGN / "restart.flag"), supervised))
    if rows:
        last = rows[-1]
        quiet = int(time.time() - _stamp(last["at"])) // 60
        # A builder in flight writes no events; silence with a live model call is
        # a long build, not a stall (T1 sat 23 quiet minutes while its worktree
        # visibly moved). A gate writes none either, and the combined gate before
        # a keep runs several suites: a driver with any child is working.
        busy = any("model call" not in line and ("reviewer" in line or "builder" in line)
                   for line in calls_in_flight()) or driver_is_working(driver_pid)
        if quiet >= 20 and not busy:
            lines.append(f"  !! nothing has happened for {quiet} minutes and no model "
                         "call is in flight — check the driver")
        accepted_rows = [row for row in rows if row.get("kind") == "accepted"]
        if accepted_rows:
            ago = int(time.time() - _stamp(accepted_rows[-1]["at"])) // 3600
            if ago >= 3:
                # the bare fact only: an old accepted event proves neither a
                # kept commit nor a running loop, so the line claims neither
                lines.append(f"  !! nothing accepted for {ago} hours")
    try:
        from backlog import Backlog
        from doctor import diagnose
        complaints = diagnose(Backlog(_current_backlog(CAMPAIGN)), Workspace(CAMPAIGN), rows)
        doctor = [f"  !! {row.about}: {row.what} → {row.do}" for row in complaints]
    except (OSError, ValueError, KeyError) as error:
        doctor = [f"  !! the doctor itself failed: {error}"]
    flagged = stamped(lines + doctor, "warnings", CAMPAIGN)
    return flagged if everything else flagged[:len(lines) + 4]


def _stamp(at: str) -> float:
    try:
        return datetime.datetime.strptime(at + "+0000", "%Y-%m-%dT%H:%M:%SZ%z").timestamp()
    except ValueError:
        return 0.0


def alerts(everything: bool = False) -> list[str]:
    """Everything asking for a person, oldest first. `everything` is the alarm path
    (`--check`): the cut to four is the screen's alone, made AFTER `stamped`, or the
    fifth alert loses its first-seen time and never reaches the 15-minute email. The
    emptiness is stamped too, or a cleared alert that returns inherits an age it has
    not. What is SHOWN is marked by the last displayed row's line number
    (`alerts_snapshot`); the alarm shows to nobody, so it marks nothing."""
    space = Workspace(CAMPAIGN)
    rows, at = space.alerts_snapshot()
    lines = stamped([f"    {line}" for line in rows], "alerts", CAMPAIGN)
    if not rows:
        return []
    shown = lines if everything else lines[:4]
    if not everything:
        space.alerts_shown(at[len(shown) - 1] + 1)          # the line it stopped at
    return [f"  *** {len(rows)} THINGS ASKING FOR A PERSON ***"] + shown


SECTIONS = [("the loop", health), ("", warnings), ("", alerts),
            ("model calls in flight", calls_in_flight),
            ("the backlog", backlog), ("what happened last", last_events),
            ("the live task's worktree", live_worktree),
            ("accepted work", accepted),
            ("where the time goes", time_report)]


def red_flags() -> list[str]:
    """Only what is wrong: a dead supervisor or a stop flag, the warning lines,
    and the alerts. Empty means `--check` exits 0."""
    return health_failures() + warnings(everything=True) + alerts(everything=True)


def main(verbose: bool = False) -> str:
    now = datetime.datetime.now(datetime.timezone.utc).astimezone()
    lines = [f"=== {now.strftime('%A %H:%M:%S %Z')}  —  the loop"]
    for title, section in SECTIONS:
        body = section()
        if not body:
            continue
        if title and title != "the loop":
            lines += ["", f"--- {title}"]
        lines += body
    if verbose:
        lines += ["", "--- the last review, in full"] + last_review()
    return "\n".join(lines)


if __name__ == "__main__":
    if "--check" in sys.argv:
        # Its own exit path: the handler below answers 0, and a check must
        # never say "green" because a pipe closed.
        flags = red_flags()
        try:
            print("\n".join(flags) if flags else "no red flags", flush=True)
        except BrokenPipeError:
            # The reader went away; hand the interpreter a sink so its own
            # shutdown flush cannot turn the exit code into 120.
            import os
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        raise SystemExit(1 if flags else 0)
    try:
        print(main(verbose="-v" in sys.argv))
    except KeyboardInterrupt:      # Ctrl-C mid-refresh: the shell says goodbye, not a traceback
        raise SystemExit(130)
    except BrokenPipeError:        # `watch.sh -1 | head` closing early is not an error
        raise SystemExit(0)
