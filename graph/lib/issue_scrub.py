"""Public draft text: remove machine identities before printing or hashing it.

The structural shapes match scrub-check.sh; session ids and absolute scratch
paths are removed too. Known account/session values come from the ledger and
cards, so a bare value is removed even without a label beside it.
"""

from __future__ import annotations

import getpass
import re

import accounts

UUID = re.compile(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", re.IGNORECASE)
IDENTITY = re.compile(
    r"\b(?:session(?:[_ -]?id)?|session_account|account(?:[_ -]?name)?|username)"
    r"[\"']?\s*[:=]\s*[\"']?([\w.@+-]+)", re.IGNORECASE)
PATH = re.compile(r"(?:file://|[A-Za-z]:[\\/]|(?<![\w/])/(?!/)|~/|[$]HOME/)[^\s\"'<>`),;]+")
HOME_USER = re.compile(r"/(?:home|Users)/([^/\s]+)")
CONFIG = re.compile(r"[.]claude-[\w-]+")
LOCALHOST = re.compile(r"127[.]0[.]0[.]1|localhost:\d+|0[.]0[.]0[.]0")


def identities(rows: list[dict], cards: list[dict]) -> set[str]:
    names = set(accounts.names()) | {getpass.getuser()}
    for row in rows + cards:
        for key in ("account", "session_account", "session", "session_id", "username"):
            if key == "account" and row.get(key) in ("gate", "plan", "lane"):
                continue  # accounting buckets, not provider identities
            if isinstance(row.get(key), str) and row[key]:
                names.add(row[key])
        resource = str(row.get("on") or "").partition(":")[2]
        if "/" in resource:
            names.add(resource.split("/", 1)[0])
    return names


def scrub(text: str, names: set[str]) -> str:
    hidden = names | set(HOME_USER.findall(text)) | set(IDENTITY.findall(text))
    text = PATH.sub("[path]", text)
    text = UUID.sub("[session]", text)
    text = CONFIG.sub("[account-config]", text)
    text = LOCALHOST.sub("[local-address]", text)
    text = re.sub(r"`[0-9a-f]{7,40}`", "[commit]", text)
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\b", "[account]", text)
    if hidden:
        pattern = r"(?<![\w-])(?:" + "|".join(re.escape(one) for one in
                                               sorted(hidden, key=len, reverse=True)) + r")(?![\w-])"
        text = re.sub(pattern, "[identity]", text)
    return text
