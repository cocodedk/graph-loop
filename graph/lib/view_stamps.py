"""First-seen stamps for the board's red flags: each `!!` line says when it
began standing, so a watcher can skip what it already sent and a person can
see age at a glance. The record follows the flags — a flag that clears and
comes back begins again, and stamping is skipped, never fatal, when the
campaign directory cannot hold the record."""

from __future__ import annotations

import datetime
import fcntl
import json
import os
import pathlib
import re


def _now() -> str:
    # seconds included: a minute-only stamp let a flag reach the staleness
    # threshold up to 59 seconds early
    return datetime.datetime.now(datetime.timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


# the whole decimal, or '1.9 hours' and '2.0 hours' normalize differently and
# a standing flag resets its stamp at the hour boundary; a falling '19.2 GB
# free' ticks the same way, and a disk that keeps filling must keep its age
TICKING = re.compile(r"\b\d+(?:\.\d+)?(?=\s*(?:minutes?|hours?|seconds?|m\b|h\b|s\b|GB\b))")


def _key(line: str) -> str:
    """A flag's identity, stable while its TIME counters tick: 'quiet for 25
    minutes' and 'quiet for 40 minutes' are the same standing flag. Only the
    number before a time unit is blanked — a task id like T25 stays itself,
    or a new T26 warning would inherit T25's age and be skipped."""
    return TICKING.sub("#", line.strip())


def stamped(lines: list[str], section: str, campaign) -> list[str]:
    """These lines, each ending `(since <when>)` — `<when>` read from the last
    call's record when the same flag stood then, this call's time otherwise.

    The record holds one namespace per section, so a caller only ever touches
    its own keys; the whole read-modify-write happens under a file lock, as
    the screen loop and the supervisor's ticker write concurrently."""
    record_path = pathlib.Path(campaign) / "flags-seen.json"
    now = _now()
    try:
        lock_handle = open(record_path.with_suffix(".lock"), "w", encoding="utf-8")  # noqa: SIM115 — closed by the with below
    except OSError:
        return [f"{line}   (since {now})" for line in lines]   # a board with no home still shows
    with lock_handle as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            record = json.loads(record_path.read_text("utf-8"))
            if not isinstance(record, dict):
                record = {}
        except (OSError, ValueError):
            record = {}
        kept = record.get(section)
        old = kept if isinstance(kept, dict) else {}
        seen = {_key(line): str(old.get(_key(line)) or now) for line in lines}
        record[section] = seen
        try:
            fresh = record_path.with_suffix(f".{os.getpid()}.new")
            fresh.write_text(json.dumps(record, indent=1), "utf-8")
            os.replace(fresh, record_path)
        except OSError:
            pass
    return [f"{line}   (since {seen[_key(line)]})" for line in lines]


if __name__ == "__main__":     # `python3 view_stamps.py < text`: its identity
    import sys
    print(TICKING.sub("#", sys.stdin.read()))
