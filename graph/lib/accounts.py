"""Every account the loop may spend, in one table.

The loop has more than one account so that an expired or exhausted one never
stops the work. That only holds if adding an account is a line of data: the
name-to-configuration mapping used to live in three places — the order in
`loop_types`, an `account == "personal"` branch in `providers`, and a second
copy in the doctor's check — so a third account could not be added without
editing code, and the two that existed disagreed about how to reach them.

One entry per account, tried in this order. `config` is the CLAUDE_CONFIG_DIR
that account needs, or None for the default configuration — which is removed
from the environment rather than set empty, because an empty value points at a
configuration holding no login.

One account is the default, because only the machine running the loop knows
where a second account's configuration lives. To add one: sign it in with its
own configuration directory, and name it in GRAPH_ACCOUNTS.
"""

from __future__ import annotations

import contextlib
import os
import pathlib

_DEFAULT = (("work", None),)
_retired: frozenset[str] = frozenset()


def table() -> tuple[tuple[str, str | None], ...]:
    """The accounts, from GRAPH_ACCOUNTS when it is set, else the one default.

    GRAPH_ACCOUNTS is `name=configdir` pairs separated by commas, a bare name
    meaning the default configuration: `work,second=/etc/claude/second`.
    """
    raw = os.environ.get("GRAPH_ACCOUNTS", "").strip()
    if not raw:
        return _DEFAULT
    out = []
    for piece in raw.split(","):
        name, _, config = piece.strip().partition("=")
        if name.strip():
            out.append((name.strip(), config.strip() or None))
    return tuple(out) or _DEFAULT


def names() -> tuple[str, ...]:
    return tuple(name for name, _ in table())


def available() -> tuple[str, ...]:
    """Configured accounts still eligible for this run."""
    return tuple(name for name in names() if name not in _retired)


@contextlib.contextmanager
def without(retired):
    """Share one fixed retirement set across the driver's lanes, only for this run."""
    global _retired
    before, _retired = _retired, frozenset(retired)
    try:
        yield available()
    finally:
        _retired = before


def home(account: str) -> pathlib.Path:
    """Where that account's credentials live, default configuration included."""
    for name, config in table():
        if name == account:
            return pathlib.Path(config).expanduser() if config else pathlib.Path.home() / ".claude"
    raise KeyError(f"no such account: {account!r}; the loop knows {names()}")


def environment(account: str) -> tuple[dict, tuple[str, ...]]:
    """What to set and what to remove for a call on this account.

    An account on the default configuration has CLAUDE_CONFIG_DIR *removed*: an
    empty one points at a configuration with no login, and the call comes back
    "Not logged in · Please run /login".
    """
    for name, config in table():
        if name == account:
            if config:
                return {"CLAUDE_CONFIG_DIR": str(pathlib.Path(config).expanduser())}, ()
            return {}, ("CLAUDE_CONFIG_DIR",)
    raise KeyError(f"no such account: {account!r}; the loop knows {names()}")
