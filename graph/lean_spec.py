"""A lean spec's record of its last run, and the checkout its next run builds in.

How the last run ended (`lean_status`, `lean_pr`, `lean_worktree`) is kept in the workspace,
`spec-<name>.json`, and the spec file is never written. A stopped spec carries on in its kept
worktree; a spec whose pull request has review findings is revised on its own branch.
"""

from __future__ import annotations

import json
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


def _kept(ws, spec_path: str) -> pathlib.Path:
    return ws.root / f"spec-{slug(spec_path)}.json"


def state(ws, spec_path: str) -> dict:
    """What the loop knows of the spec's last run (`lean_*`): the workspace's word over any an older run left
    in the spec's front matter. A field the workspace cleared is gone, whatever the front matter says."""
    try:
        kept = json.loads(_kept(ws, spec_path).read_text("utf-8"))
    except (OSError, ValueError):
        kept = {}
    older = {k: v for k, v in front(pathlib.Path(spec_path).read_text("utf-8")).items() if k.startswith("lean_")}
    return {k: v for k, v in {**older, **kept}.items() if v is not None}


def record(ws, spec_path: str, **fields: str | int | None) -> None:
    """Write `fields` into the spec's state in the workspace. The spec file is never written: its front matter
    was committed by accident, blocked `git pull`, and losing it lost the resume point. None clears a field."""
    try:
        kept = json.loads(_kept(ws, spec_path).read_text("utf-8"))
    except (OSError, ValueError):
        kept = {}
    kept.update(fields)
    _kept(ws, spec_path).write_text(json.dumps(kept), "utf-8")


def start(repo: str, feature: str, info: dict, revise: str = "") -> tuple[Worktree, str]:
    """The checkout to build in, and why the last attempt fell short ("" for a fresh one).

    Revising: the checkout starts at the pull request's branch. Stopped with its
    worktree kept: it carries on there, so the work is not thrown away and paid for
    again (delete the worktree to start fresh)."""
    if revise:
        return Worktree(repo, feature, commit=f"refs/remotes/origin/lean/{feature}").create(), revise
    tree = Worktree(repo, feature, commit=lean_git.BASE)
    kept = pathlib.Path(str(info.get("lean_worktree") or "")) if info.get("lean_status") == "stopped" else None
    if not kept or not (kept / ".git").is_dir():
        return tree.create(), ""
    note = kept / KEEP_NOTE
    last = note.read_text("utf-8").split("\n\nTask ", 1)[0] if note.is_file() else "it stopped"
    try:
        return tree.reuse(str(kept)), last
    except HeadMoved:                          # the kept work no longer fits main: start over
        return Worktree(repo, feature, commit=lean_git.BASE).create(), ""


def unstarted(ws, feature: str, error: Exception) -> str:
    """The checkout could not be cut (a full temp folder, usually): the stop is recorded and mailed, cause
    first, and "" says nothing was built. Nothing is kept in the spec's state: no tree exists to resume in."""
    why = (f"Creating the checkout failed: {str(error)[-500:]}\nIf the temp folder is full, free space in it or "
           "start the loop with TMPDIR set to a folder on a bigger disk, then run the spec again. Nothing was built.")
    ws.event("lean_stopped", task=feature, why=why)
    ws.mail_person(f"graph-loop needs you: {feature}", f"{feature} stopped.\n\nWhy:\n{why}")
    return ""


NOTES = (("rules.md", "The project's standing rules (settled: ask nothing about what they settle, and follow them)"),
         ("lessons.md", "Lessons from earlier runs of this project (hints to check, never proof)"))   # beside the specs, never specs


def lessons(folder) -> str:
    """The project's notes beside its specs as prompt sections, or "" when there are none. `rules.md` holds
    rules the project has settled: the grill asks nothing about what they settle and the builder follows them.
    `lessons.md` holds what agents keep rediscovering, one fact per line with its evidence: hints to check,
    never proof. People write both; the loop only reads them. They go to the grill and the builder, never to
    the reviewer, whose judgement stays its own."""
    out = ""
    for name, heading in NOTES:
        path = pathlib.Path(folder) / name
        if path.is_file() and (text := path.read_text("utf-8").strip()):
            out += f"\n\n## {heading}\n\n{text}"
    return out


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

