"""A project's lean specs and the mark each one carries."""

from __future__ import annotations

import pathlib
import re
import subprocess

import lean_spec
import project_cost
import yaml  # type: ignore[import-untyped]  # no stubs in this environment

BUILT, BUILDING, STOPPED, PR_OPEN, WAITING = "✔ built", "▶ building", "✖ stopped", "● pr open", "· waiting"
QUESTION = "? awaiting answer"   # the grill sent it back: a person has to answer
MARKS = (BUILT, BUILDING, STOPPED, QUESTION, PR_OPEN, WAITING)   # the order the first line counts them in
MARK_STYLE = {BUILT: "green", BUILDING: "yellow", STOPPED: "red", QUESTION: "magenta", PR_OPEN: "cyan", WAITING: "dim"}
LOGGED = {"lean_feature_started": None, "lean_stopped": "stopped", "lean_published": "pr_open"}   # event -> status
REFS = ("origin/main", "main")


def spec_files(project: str) -> list[pathlib.Path]:
    """The `*.md` files of `docs/lean` except the notes beside them (`lean_spec.NOTES`), by file name."""
    folder = pathlib.Path(project) / "docs" / "lean"
    return sorted((path for path in folder.glob("*.md") if path.is_file() and path.name not in dict(lean_spec.NOTES)),
                  key=lambda path: path.name)


def commits(project: str) -> list[tuple[str, str]] | None:
    """The commits on origin/main, else main, newest first, as (subject, body); None when git gives neither.
    The whole message is read: the person merging can type their own subject, and the squash body still
    holds `* feat(<spec>): ...`."""
    for ref in REFS:
        try:
            done = subprocess.run(["git", "-C", project, "log", "--format=%x01%s%x02%b", ref],
                                  capture_output=True, text=True, errors="replace", check=False)
        except OSError:
            return None
        if done.returncode == 0:
            return [(subject, body) for subject, _, body in
                    (chunk.partition("\x02") for chunk in done.stdout.split("\x01")[1:])]
    return None


def _scopes(commit: tuple[str, str]) -> list[str]:
    """The spec names a commit says it built: every line of its message that starts `feat(<name>)`,
    optionally after `* `. A mention in mid-sentence is not one."""
    return [found.group(1) for line in (commit[0], *commit[1].splitlines())
            if (found := re.match(r"(?:\* )?feat\(([^)]+)\)", line))]


def built_from(found: list[tuple[str, str]] | None) -> set[str] | None:
    """The names with a `feat(<name>)` line in a commit message, which is what the loop's squash merge leaves."""
    return None if found is None else {name for commit in found for name in _scopes(commit)}


def built_names(project: str) -> set[str] | None:
    """The names built according to origin/main, else main; None when git gives neither."""
    return built_from(commits(project))


def recent(found: list[tuple[str, str]] | None, specs: set[str], count: int = 8) -> list[str]:
    """The subjects of the latest commits that are not a spec's own merge (a `feat(<spec>)` line with a numbered
    scope or a spec's name, in the subject or the body): what was merged by hand."""
    return [subject for subject, body in found or []
            if not any(name[:1].isdigit() or name in specs for name in _scopes((subject, body)))][:count]


def logged_status(path: pathlib.Path) -> str | None:
    """What the project's event log says of the spec: the newest event that names it decides. A grill with
    questions waits for an answer, a stop and a publish say so, a newer start or a clear grill says nothing."""
    name, status = lean_spec.slug(path.name), None
    for row in project_cost._rows(str(path.absolute().parents[2])):
        kind = row.get("kind")
        if kind == "lean_grilled":
            if isinstance(row.get("specs"), list) and name in row["specs"]:
                status = "questions" if row.get("questions") else None
        elif row.get("task") == name and isinstance(kind, str) and kind in LOGGED:
            status = LOGGED[kind]
    return status


def status_of(path: pathlib.Path) -> object:
    """The spec's `lean_status`, else what the event log says; None when neither names one."""
    try:
        matter = lean_spec.front(path.read_text("utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return None
    status = matter.get("lean_status") if isinstance(matter, dict) else None
    return logged_status(path) if status is None else status


def mark(path: pathlib.Path, running: set[str], built: set[str] | None) -> str:
    """The first mark that holds: building, built (a `feat(<spec>)` commit line, or a person's `lean_status: built`), stopped, question, pr open, waiting."""
    name = lean_spec.slug(path.name)
    if name in running:
        return BUILDING
    if built and name in built:
        return BUILT
    status = status_of(path)
    return {"built": BUILT, "stopped": STOPPED, "questions": QUESTION, "pr_open": PR_OPEN}.get(str(status), WAITING)
