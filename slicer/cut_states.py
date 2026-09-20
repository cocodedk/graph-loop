"""The three states a campaign's cut review can be in: off, observe, act."""

from __future__ import annotations

import datetime
import pathlib

import yaml  # type: ignore[import-untyped]

FILE = "cut-states.yaml"


def _read(campaign: pathlib.Path) -> dict:
    path = pathlib.Path(campaign) / FILE
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text("utf-8")) or {}


def load(campaign: pathlib.Path) -> str:
    """The current state; "off" when nothing has ever been switched."""
    return _read(campaign).get("state", "off")


def switch(campaign: pathlib.Path, to: str, by: str) -> None:
    """Set the state and add one entry to the history, keeping the earlier ones."""
    campaign = pathlib.Path(campaign)
    history = list(_read(campaign).get("history") or [])
    at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    history.append({"to": to, "by": by, "at": at})
    beside = campaign / f"{FILE}.new"
    beside.write_text(yaml.safe_dump({"state": to, "history": history}, sort_keys=False), "utf-8")
    beside.replace(campaign / FILE)
