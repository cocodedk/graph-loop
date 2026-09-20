"""The supervisor's fatal notice: written when it stands down, taken off the
board only by a delivery that carried it.

`supervisor.sh` writes `stand-down.txt` when the driver has died five times and
nothing is left running; `view_pulse.py` puts its words on every check, with
the board's own age after them; `alert-watcher.sh` clears it here — and
only when the payload just delivered contains those words, because delivering an older,
unrelated board must never take away a notice nobody has read. The write and
the clearing share `stand-down.lock`, so a notice written between the reading
and the removing is not deleted unread.

    python3 notice.py <campaign-dir> < the-payload-just-delivered   # clear it
    python3 notice.py --audience  < the-board    # what to tell the messenger
    python3 notice.py --mail      < the-board    # the lines a mail may carry,
                                                 # exit 1 when there are none
"""

from __future__ import annotations

import fcntl
import pathlib
import sys

DISK = "DISK NEARLY FULL"                  # view_pulse writes the line; this names it
STOOD_DOWN = "the supervisor stood down"   # supervisor.sh's own first words


def fatal(text: str) -> bool:
    """Whether these board lines carry something only a person can clear.

    One thing is: a dead loop — the stand-down above — which is infrastructure
    and the single human matter left (CLAUDE.md § Code). A disk about to fill is
    not a second route to the owner: it stands the supervisor DOWN (supervisor.sh
    starts no driver on it), and the notice that stand-down writes carries the
    disk words inside it, so one route delivers both (astra round 4, finding
    16; the warning used to be mailed while the loop kept running).
    Everything else on the board is answered by the decision about its card — a
    mail about it is a handoff to somebody who is not coming (round-3 finding
    18). `stale_flags` and `alert-watcher.sh` both read this, so the escalation
    and the words sent to the messenger can never disagree about what is fatal.
    """
    return STOOD_DOWN in text


def audience(text: str) -> str:
    """What the messenger is told about who may be handed these flags."""
    if fatal(text):
        return ("This board carries a FATAL flag — the supervisor stood down, so nothing "
                "is running. That one is the owner's: tell them, with exactly what you need. "
                "Everything else below is yours.")
    return ("None of this waits for a person: decide it, or record what the repository "
            "cannot answer as a gap on the card it belongs to.")


def body(text: str) -> str:
    """The notice's own words, whole: its first line, nothing dropped.

    Every word counts, because the run that wrote it is in there — two
    stand-downs say the same thing otherwise, and dropping the part that told
    them apart let the delivery of an older board take away a newer notice
    nobody had read. The board adds its own age AFTER these words, so a payload
    carries a notice when it contains them."""
    said = [line for line in text.splitlines() if line.strip()]
    return said[0].rstrip() if said else ""


def clear(campaign: str | pathlib.Path, payload: str) -> bool:
    """Remove the notice if `payload` carried its words; say whether it went."""
    camp = pathlib.Path(campaign)
    try:
        lock_handle = open(camp / "stand-down.lock", "w", encoding="utf-8")  # noqa: SIM115 — closed by the with below
    except OSError:
        return False
    with lock_handle as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        notice = camp / "stand-down.txt"
        try:
            said = body(notice.read_text("utf-8"))
        except OSError:
            return False
        if not said or said not in payload:
            return False
        notice.unlink(missing_ok=True)
        return True


if __name__ == "__main__":
    if sys.argv[1:] == ["--audience"]:
        print(audience(sys.stdin.read()))
        raise SystemExit(0)
    if sys.argv[1:] == ["--mail"]:
        # a mail carries only what a person can clear, and a board with none of
        # it is not a mail at all: exit 1 says so to the caller
        said = [line for line in sys.stdin if fatal(line)]
        sys.stdout.writelines(said)
        raise SystemExit(0 if said else 1)
    raise SystemExit(0 if clear(sys.argv[1], sys.stdin.read()) else 1)
