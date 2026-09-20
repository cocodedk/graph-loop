"""Small durable records owned by the standalone slicer."""

from __future__ import annotations

import hashlib
import pathlib
import sys

import yaml  # type: ignore[import-untyped]

DRIVE_LIB = pathlib.Path(__file__).resolve().parents[1] / "drive" / "lib"
sys.path.insert(0, str(DRIVE_LIB))
from backlog import Backlog  # type: ignore[import-not-found]

STATE = ".slicer-state.yaml"


def forget(backlog: pathlib.Path) -> None:
    """Drop the coverage record. What it was accepted for is no longer there."""
    (backlog / STATE).unlink(missing_ok=True)


def trace(backlog: pathlib.Path, step: str, **detail) -> None:
    """One JSONL line per step the slicer takes — the owner's order: every step
    findable afterwards. Append-only beside the backlog; never fatal."""
    import datetime
    import json
    line = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "step": step, **detail}
    try:
        with open(backlog / ".slicer-trace.jsonl", "a", encoding="utf-8") as out:
            out.write(json.dumps(line, default=str) + "\n")
    except OSError:
        pass


def close(backlog: pathlib.Path, sources: list[pathlib.Path], verdict: str,
          root: pathlib.Path, rows: list[dict]) -> None:
    """Record what was accepted: the sources AND the molecules the reviewer was
    shown. `rows` is the caller's own list — the one the coverage prompt was
    built from — never re-read here, or a card that changed while the review ran
    would be recorded as covered by a verdict about a backlog it was not in."""
    state = {"source_digest": digest(sources, root), "backlog_digest": backlog_digest(rows),
             "review": verdict}
    with Backlog(backlog).only_writer():
        beside = backlog / f"{STATE}.new"
        beside.write_text(yaml.safe_dump(state, sort_keys=False), "utf-8")
        beside.replace(backlog / STATE)


def covered(backlog: pathlib.Path, sources: list[pathlib.Path],
            root: pathlib.Path, rows: list[dict]) -> bool:
    if not (backlog / STATE).exists():
        return False
    if _record(backlog).get("source_digest") == digest(sources, root) \
            and accepted(backlog, rows):
        return True
    forget(backlog)
    return False


def accepted(backlog: pathlib.Path, rows: list[dict]) -> bool:
    """Whether an accepted coverage still stands for these backlog contracts.

    A read, and only a read. The sources are the slicer's own judgement, made
    against the clean checkout of the campaign branch it plans in; a caller
    that hashed them from another root — the driver's working tree, with
    somebody's uncommitted edit in it — would disagree with the record and
    delete a verdict that was right."""
    return _record(backlog).get("backlog_digest") == backlog_digest(rows)


def _record(backlog: pathlib.Path) -> dict:
    try:
        return yaml.safe_load((backlog / STATE).read_text("utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def backlog_digest(rows: list[dict]) -> str:
    """Every card's declared contract, digested.

    The complete contract, not the roster line the reviewer reads: a card
    removed, renamed, refiled, or rewritten to run a different gate or finish
    on a different condition is a backlog the accepted verdict was never about,
    whether or not the reviewer was shown that field. Settled cards count too —
    a rewrite of finished work still has to be looked at again. Imported inside
    the call because `asking` reads `files` from here."""
    from asking import contract_text  # the pair import each other
    return hashlib.sha256(contract_text(rows).encode()).hexdigest()


def digest(sources: list[pathlib.Path], root: pathlib.Path) -> str:
    """Stable across checkout roots AND sensitive to moves: each file hashes
    as its repo-relative path plus its bytes, so two clean worktrees agree
    and a renamed source is news."""
    answer = hashlib.sha256()
    for path in sorted(files(sources)):
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        answer.update(str(rel).encode()); answer.update(b"\0"); answer.update(path.read_bytes())
    return answer.hexdigest()


def files(sources: list[pathlib.Path]) -> list[pathlib.Path]:
    found: list[pathlib.Path] = []
    for source in sources:
        if source.is_dir():
            found.extend(path for path in source.rglob("*") if path.is_file())
        elif source.is_file():
            found.append(source)
        else:
            raise ValueError(f"approved source does not exist: {source}")
    return sorted(found)


def inside(repo: pathlib.Path, paths: list[pathlib.Path], what: str) -> None:
    for path in paths:
        if not path.is_relative_to(repo):
            raise ValueError(f"{what} is outside the repository: {path}")
        if not path.exists():
            raise ValueError(f"{what} does not exist: {path}")


def record(where: pathlib.Path, question: str, answer: str,
           folder: str = ".slicer-calls") -> None:
    """Every prompt and every answer, kept where the planner will not read them.

    `where` is the CAMPAIGN directory when there is one. These used to be
    written inside the repository the planner is then told to read, so a retry
    was not independent: it found its own refused answer and reused it. The
    planner said so in its own words — "This exact spec already exists at
    `.speccer-calls/0001-answer.yaml` — I'll reuse it" — and three retries of one
    branch failed identically, while clearing the directory and changing nothing
    else got a spec on the second try (2026-09-18).

    The step trace stays beside the backlog: it holds attempt numbers and
    refusal reasons, not answers, so reading it back tells the planner that a
    round failed and never what it wrote.
    """
    calls = where / folder
    calls.mkdir(parents=True, exist_ok=True)
    number = len(list(calls.glob("*-prompt.txt"))) + 1
    (calls / f"{number:04d}-prompt.txt").write_text(question, "utf-8")
    (calls / f"{number:04d}-answer.yaml").write_text(answer, "utf-8")
