"""A lean spec file's own record, and the checkout its next run builds in.

The front matter says how the last run ended (`lean_status`, `lean_pr`,
`lean_worktree`). A stopped spec carries on in its kept worktree; a spec whose
pull request has review findings is revised on its own branch.
"""

from __future__ import annotations

import pathlib

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
    if not cardfile.FRONT.match(text):      # a spec with no front matter gets one
        text = f"---\n{yaml.safe_dump(fields, sort_keys=False)}---\n{text}"
    for field, value in fields.items():
        text = cardfile.patch(text, field, value)
    path.write_text(text, "utf-8")


def start(repo: str, feature: str, spec: str, revise: str = "") -> tuple[Worktree, str, str]:
    """The checkout to build in, why the last attempt fell short ("" for a fresh one),
    and the commit the reviewer diffs against ("" for the checkout's own base).

    Revising: the checkout starts at the pull request's branch and the reviewer sees
    the whole feature against main. Stopped with its worktree kept: it carries on
    there, so the work is not thrown away and paid for again (delete the worktree
    to start fresh)."""
    if revise:
        tree = Worktree(repo, feature, commit=f"refs/remotes/origin/lean/{feature}").create()
        return tree, revise, lean_git.fork_point(repo, feature)
    tree = Worktree(repo, feature, commit=lean_git.BASE)
    info = front(spec)
    kept = pathlib.Path(str(info.get("lean_worktree") or "")) if info.get("lean_status") == "stopped" else None
    if not kept or not (kept / ".git").is_dir():
        return tree.create(), "", ""
    note = kept / KEEP_NOTE
    last = note.read_text("utf-8").split("\n\nTask ", 1)[0] if note.is_file() else "it stopped"
    try:
        return tree.reuse(str(kept)), last, ""
    except HeadMoved:                          # the kept work no longer fits main: start over
        return Worktree(repo, feature, commit=lean_git.BASE).create(), "", ""
