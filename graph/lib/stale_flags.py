"""Email a FATAL red flag that has stood for more than 15 minutes — mechanical,
and only when nobody is already on it (WATCHER or its stand-in, by a fresh
heartbeat); the owner's order is "for now everything is in your hands", so the
mail is for when nobody can be reached, not a running board.

Fatal is `notice.fatal`: the supervisor's stand-down, the one thing a person
alone can clear. An ordinary flag is answered by the decision about its card
and never reaches a mailbox — the loop does not wait for a person to read text
(CLAUDE.md § Code, astra's round-3 finding 18). A disk about to fill is not a
route of its own either: it stands the supervisor down, and its words are
inside that notice (round-4 finding 16).

Run by the supervisor's ticker on every red check. Each flag is emailed ONCE
per first-seen stamp: the same standing flag never repeats, however long it
stands, and a flag that clears and comes back is news again. A flag held
because someone is watching stays out of the sent-record, so it is still
news the moment nobody is. The record of what was emailed lives in the
campaign (`flags-emailed.json`) and drops keys the board no longer shows.

    python3 stale_flags.py <campaign-dir> <check-output-file>
"""

from __future__ import annotations

import datetime
import json
import pathlib
import re
import sys

from alert_email import send
from heartbeat_age import watching
from notice import fatal
from view_stamps import TICKING

STALE_MINUTES = 15
LINE = re.compile(r"^(.*)\(since ([0-9T:+-]+)\)\s*$")


def standing(lines: list[str], now: datetime.datetime):
    """(key, line, stale) per stamped flag. The key is the flag's identity: its
    text with every number blanked, plus its first-seen stamp — a counter that
    ticks ('quiet for 25 minutes' → '40 minutes') is the SAME flag and must
    not be emailed again, while a flag that cleared and returned carries a new
    stamp and is news."""
    for raw in lines:
        m = LINE.match(raw.strip())
        if not m:
            continue
        seen = None
        for shape in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M%z"):   # older stamps carry no seconds
            try:
                seen = datetime.datetime.strptime(m.group(2), shape)  # noqa: DTZ007 — every shape carries %z
                break
            except ValueError:
                continue
        if seen is None:
            continue
        key = TICKING.sub("#", m.group(1)).strip() + "|" + m.group(2)
        yield key, raw.strip(), (now - seen).total_seconds() >= STALE_MINUTES * 60


def main(camp: str, check: str) -> int:
    record_path = pathlib.Path(camp) / "flags-emailed.json"
    try:
        sent = json.loads(record_path.read_text("utf-8"))
        if not isinstance(sent, dict):
            sent = {}
    except (OSError, ValueError):
        sent = {}
    now = datetime.datetime.now(datetime.timezone.utc)
    lines = pathlib.Path(check).read_text("utf-8").splitlines()
    current = {key: (line, stale) for key, line, stale in standing(lines, now)}
    news = {key: line for key, (line, stale) in current.items()
            if stale and key not in sent and fatal(line)}
    # keys the board no longer shows drop out; a returning flag has a new stamp
    keep = {key: sent[key] for key, (_, stale) in current.items()
            if stale and key in sent}
    watcher = watching(camp)
    if news and watcher:
        # held, not sent: news keys stay out of keep, so they are still news
        # the moment both heartbeats go stale
        print(f"escalation held: {watcher} is watching")
    elif news:
        try:
            send(f"{len(news)} red flag(s) stood for at least {STALE_MINUTES} minutes",
                 "\n".join(news.values()), important=True)
            # recorded only AFTER the send: a mail failure retries next tick
            keep.update({key: now.strftime("%Y-%m-%dT%H:%M%z") for key in news})
        except BaseException:
            record_path.write_text(json.dumps(keep, indent=1), "utf-8")
            raise
    record_path.write_text(json.dumps(keep, indent=1), "utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
