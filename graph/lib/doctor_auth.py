"""An account that cannot sign in, read from the credential it holds.

The work account's session expired overnight and the board said nothing: every
call on it was refused and the loop fell through to the other account, so the
work kept landing and the failure hid behind it.

The first version of this check read the answers on disk instead, and went on
complaining for hours after the account was signed in again, because the
refusals were still in its window. A stale complaint teaches a reader to ignore
the board. This reads what is true now: an account is well when its credential
has not expired, or can refresh itself.
"""

from __future__ import annotations

import contextlib
import json
import pathlib
import time

import accounts
from doctor_types import Complaint

# The accounts and where their credentials live come from one table, so this
# check cannot disagree with the calls about how an account is reached.


def check_auth(_campaign: pathlib.Path | None = None, homes=None) -> list[Complaint]:
    """Every account whose stored credential cannot answer a call right now."""
    dead = _dead(homes)
    return [_complaint(dead)] if dead else []


def _dead(homes=None) -> list[tuple[str, str]]:
    homes = homes if homes is not None else [(name, str(accounts.home(name)))
                                             for name in accounts.names()]
    return [(name, home) for name, home in homes
            if not _can_sign_in(pathlib.Path(home).expanduser())]


def _complaint(dead) -> Complaint:
    return Complaint(
        "an account", f"{', '.join(name for name, _ in dead)} cannot sign in: the stored session has expired and carries no "
        "refresh token, so every call on it is refused",
        " and ".join(f"`{_login(name, home)}`" for name, home in dead))


@contextlib.contextmanager
def run_accounts(space):
    """Retire known unusable accounts before routing, with one alert for the run."""
    dead = _dead()
    if dead:
        complaint = _complaint(dead)
        why = f"{complaint.what}; retired for this run. Sign in with {complaint.do}"
        space.alert(complaint.about, why, limit=None)  # keep every account's login command
        print(why)
    with accounts.without(name for name, _ in dead) as remaining:
        yield remaining


def _login(name: str, home: str) -> str:
    """The command that signs that account in, from its own configuration."""
    _, drop = accounts.environment(name) if name in accounts.names() else ({}, ())
    return ("env -u CLAUDE_CONFIG_DIR claude /login" if drop
            else f"CLAUDE_CONFIG_DIR={home} claude /login")


def _can_sign_in(home: pathlib.Path) -> bool:
    """A credential that is still valid, or can renew itself, can answer a call.

    Whatever the file holds is untrusted input: a shape we cannot read is not a
    dead account, because guessing would cry wolf, and the calls themselves say
    so soon enough.
    """
    try:
        stored = json.loads((home / ".credentials.json").read_text("utf-8"))
    except (OSError, ValueError):
        return True
    if not isinstance(stored, dict):
        return True
    nested = stored.get("claudeAiOauth")
    oauth = nested if isinstance(nested, dict) else stored
    if oauth.get("refreshToken"):
        return True
    expires = oauth.get("expiresAt")
    return not isinstance(expires, (int, float)) or expires / 1000 > time.time()
