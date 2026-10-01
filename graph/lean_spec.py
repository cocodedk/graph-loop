"""A lean spec file's own record, and the checkout its next run builds in.

The front matter says how the last run ended (`lean_status`, `lean_pr`,
`lean_worktree`). A stopped spec carries on in its kept worktree; a spec whose
pull request has review findings is revised on its own branch.
"""

from __future__ import annotations

import pathlib
import re

import cardfile
import lean_git
import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from worktree import KEEP_NOTE, Worktree
from worktree_refs import HeadMoved


def front(spec: str) -> dict:
    """The spec text's front matter, {} when it has none."""
    matter = cardfile.FRONT.match(spec)
    return (yaml.safe_load(matter["front"]) or {}) if matter else {}


def record(spec_path: str, **fields: str) -> None:
    """Write `fields` into the spec file's front matter, every other byte left alone."""
    path = pathlib.Path(spec_path)
    text = path.read_text("utf-8")
    if not cardfile.FRONT.match(text):      # a spec with no front matter gets one (a None field removes: none to write)
        text = f"---\n{yaml.safe_dump({k: v for k, v in fields.items() if v is not None}, sort_keys=False)}---\n{text}"
    for field, value in fields.items():
        text = cardfile.patch(text, field, value)
    path.write_text(text, "utf-8")


def start(repo: str, feature: str, spec: str, revise: str = "") -> tuple[Worktree, str]:
    """The checkout to build in, and why the last attempt fell short ("" for a fresh one).

    Revising: the checkout starts at the pull request's branch. Stopped with its
    worktree kept: it carries on there, so the work is not thrown away and paid for
    again (delete the worktree to start fresh)."""
    if revise:
        return Worktree(repo, feature, commit=f"refs/remotes/origin/lean/{feature}").create(), revise
    tree = Worktree(repo, feature, commit=lean_git.BASE)
    info = front(spec)
    kept = pathlib.Path(str(info.get("lean_worktree") or "")) if info.get("lean_status") == "stopped" else None
    if not kept or not (kept / ".git").is_dir():
        return tree.create(), ""
    note = kept / KEEP_NOTE
    last = note.read_text("utf-8").split("\n\nTask ", 1)[0] if note.is_file() else "it stopped"
    try:
        return tree.reuse(str(kept)), last
    except HeadMoved:                          # the kept work no longer fits main: start over
        return Worktree(repo, feature, commit=lean_git.BASE).create(), ""


def lessons(folder) -> str:
    """The project's lessons from earlier runs, `lessons.md` beside its specs, as a prompt section,
    or "" when there are none. People write them, one fact per line with its evidence; the loop only
    reads them. They go to the grill and the builder, never to the reviewer, whose judgement stays
    its own."""
    path = pathlib.Path(folder) / "lessons.md"
    text = path.read_text("utf-8").strip() if path.is_file() else ""
    return f"\n\n## Lessons from earlier runs of this project (hints to check, never proof)\n\n{text}" if text else ""


def slug(path: str) -> str:
    """The feature's name, from its spec file's name."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", pathlib.Path(path).stem).strip("-") or "feature"


def card_gate(spec: str) -> str:
    """The card's own fast gate, `gate:` in its front matter: one line of text, or "" for none."""
    gate = front(spec).get("gate")
    return gate.strip() if isinstance(gate, str) and gate.strip() and "\n" not in gate.strip() else ""


ASKED_LIMIT = 6000   # characters of the grill's questions the spec keeps: a dozen long ones fit
CUT_NOTE = "\n[cut: the mail has the whole list]"   # what ends a list that does not
GRILL_ROUNDS = 4   # the fourth real refusal goes on: late questions were mostly detail a builder can settle


def rounds(info: dict) -> int:
    """How many real refusals the grill has given this spec (`lean_rounds`); 0 when none is recorded."""
    count = info.get("lean_rounds")
    return count if isinstance(count, int) and not isinstance(count, bool) and count > 0 else 0


def refused(events: list[dict]) -> bool:
    """Whether the grill's last answer was a real refusal (a REJECT verdict), not a failure to answer."""
    grilled = [row for row in events if row.get("kind") == "lean_grilled"]
    return bool(grilled) and grilled[-1].get("verdict") == "REJECT"
