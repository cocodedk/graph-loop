"""A project's lean specs and the mark each one carries."""

from __future__ import annotations

import pathlib
import subprocess

import lean_spec
import yaml  # type: ignore[import-untyped]  # no stubs in this environment

BUILT, BUILDING, STOPPED, PR_OPEN, WAITING = "✔ built", "▶ building", "✖ stopped", "● pr open", "· waiting"
QUESTION = "? question"   # the grill sent it back: a person has to answer
MARKS = (BUILT, BUILDING, STOPPED, QUESTION, PR_OPEN, WAITING)   # the order the first line counts them in
REFS = ("origin/main", "main")


def spec_files(project: str) -> list[pathlib.Path]:
    """The `*.md` files of `docs/lean` except `lessons.md`, by file name."""
    folder = pathlib.Path(project) / "docs" / "lean"
    return sorted((path for path in folder.glob("*.md") if path.is_file() and path.name != "lessons.md"),
                  key=lambda path: path.name)


def built_names(project: str) -> set[str] | None:
    """The names with a `feat(<name>)` commit on origin/main, else main; None when git gives neither."""
    for ref in REFS:
        try:
            done = subprocess.run(["git", "-C", project, "log", "--format=%s", ref],
                                  capture_output=True, text=True, errors="replace", check=False)
        except OSError:
            return None
        if done.returncode == 0:
            return {line[5:line.index(")")] for line in done.stdout.splitlines()
                    if line.startswith("feat(") and ")" in line}
    return None


def status_of(path: pathlib.Path) -> object:
    """The spec's `lean_status`; None when the file or its front matter cannot be read."""
    try:
        matter = lean_spec.front(path.read_text("utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return None
    return matter.get("lean_status") if isinstance(matter, dict) else None


def mark(path: pathlib.Path, running: set[str], built: set[str] | None) -> str:
    """The first mark that holds: building, built, stopped, question, pr open, waiting."""
    name = lean_spec.slug(path.name)
    if name in running:
        return BUILDING
    if built and name in built:
        return BUILT
    status = status_of(path)
    return {"stopped": STOPPED, "questions": QUESTION, "pr_open": PR_OPEN}.get(str(status), WAITING)
