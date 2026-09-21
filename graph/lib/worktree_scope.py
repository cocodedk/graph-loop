"""What a task's worktree touched, judged against what the task owns.

Read from git, never from a list kept by hand: a builder that creates a file
nobody expected is caught as surely as one that edits it. Split out of
`worktree` at the 200-line cap; `worktree` stays the front door.
"""

from __future__ import annotations

import pathlib
import subprocess

ARTEFACTS = ("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".coverage",
             "node_modules", ".venv")


def _git(tree: str, *args: str) -> str:
    """A git call that fails is never read as "nothing changed": the scope check
    would return an empty list and let every change through."""
    done = subprocess.run(("git", "-C", tree, *args), capture_output=True, text=True, check=False)
    if done.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {tree}: {done.stderr.strip()[:200]}")
    return done.stdout


def _ls_tree_z(tree: str, *args: str) -> list[str]:
    """NUL-terminated records: a plain newline or whitespace split corrupts a
    tracked path that has a space (or other unusual byte) in it."""
    return _git(tree, "ls-tree", "-z", *args).split("\0")[:-1]


def _status_z(tree: str) -> list[tuple[str, str, str | None]]:
    """(code, path, source) triples from `git status --porcelain -z`:
    NUL-terminated like `_ls_tree_z`, so a path with a space, tab or quote
    parses correctly instead of being C-quoted. A rename or copy record
    carries a SECOND NUL-terminated field, the new path first then the
    original -- kept here as its OWN field, `source`, rather than folded
    into a single joined string: a filename that itself contains " -> "
    would otherwise make the join ambiguous to split back apart."""
    tokens = iter(_git(tree, "status", "--porcelain", "-uall", "-z").split("\0")[:-1])
    out = []
    for token in tokens:
        code, path = token[:2], token[3:]
        source = next(tokens) if code[0] in "RC" or code[1] in "RC" else None
        out.append((code, path, source))
    return out


def _head_files(tree: str) -> set:
    return set(_ls_tree_z(tree, "-r", "--name-only", "HEAD"))


def _gitlinks(tree: str) -> set:
    """Paths git holds as another repository (mode 160000): a committed nested
    repo is staged as a plain `A  pkg/inner`, and it is a directory, not a file."""
    records = _git(tree, "ls-files", "--stage", "-z").split("\0")[:-1]
    return {record.split("\t", 1)[1] for record in records if record.startswith("160000")}


def _siblings(tree: str, allowed: set) -> set:
    """The directories a task may add files to: the directory of each owned
    FILE. HEAD decides first: a path that is a file in HEAD (not a gitlink)
    is a file; a path with entries beneath it in HEAD is a directory,
    whatever the builder did to it on disk since. Only a path HEAD says
    nothing about falls back to disk: a file or symlink there counts,
    anything else does not. So an owned `pkg` -- tracked, replaced, or
    deleted -- never opens its parent to files it was not given."""
    head = _head_files(tree)
    head_links = {line.split("\t", 1)[1] for line in _ls_tree_z(tree, "-r", "HEAD")
                  if line.startswith("160000")}   # HEAD's own gitlinks, not the index's -- may diverge
    head_files = head - head_links
    head_dirs = {str(parent) for path in head for parent in pathlib.PurePosixPath(path).parents}
    files = {path for path in allowed
             if path in head_files
             or (path not in head and path not in head_dirs
                 and (pathlib.Path(tree, path).is_file() or pathlib.Path(tree, path).is_symlink()))}
    return {str(pathlib.PurePosixPath(path).parent) for path in files}


def _owned(path: str, allowed_set: set, in_head: set) -> bool:
    """An owned FILE owns nothing beneath it: replaced by a directory of the same
    name it would carry its children in. An owned directory still does."""
    return any(path == ok or (path.startswith(ok + "/") and ok not in in_head)
               for ok in allowed_set)


def _is_artefact(path: str) -> bool:
    return any(part in ARTEFACTS for part in path.rstrip("/").split("/")) or path.endswith(".pyc")


def changed_outside(tree: str, allowed: list[str], may_add: bool = False) -> list[str]:
    """Every path this tree touched that its task was not given.

    Read from git rather than from a list somebody keeps by hand, so a builder
    that creates a file nobody expected is caught as surely as one that edits it.
    `may_add` also allows NEW FILES beside the task's own — the one thing a file
    list cannot express, the 200-line split. A rename or copy carries two real
    paths, kept apart by `_status_z`; each endpoint is judged on its own —
    owned, or noise — so a grant or a build artefact at one end can never
    smuggle an ordinary ungranted change at the other past the check.
    """
    allowed_set = {path.rstrip("/") for path in allowed}
    in_head = _head_files(tree)
    gitlinks = _gitlinks(tree)
    beside = _siblings(tree, allowed_set) if may_add else set()
    out = []
    for code, path, source in _status_z(tree):
        if not path:
            continue
        endpoints = (source, path) if source is not None else (path,)
        if all(_owned(endpoint, allowed_set, in_head) or _is_artefact(endpoint)
               for endpoint in endpoints):
            continue
        if (code in ("??", "A ", " A", "AM") and not path.endswith("/")
                and path not in gitlinks
                and str(pathlib.PurePosixPath(path).parent) in beside):
            continue   # a new FILE beside the task's own; a directory or nested repo never
        out.append(f"{source} -> {path}" if source is not None else path)
    return sorted(out)


def added_beside(tree: str, allowed: list[str]) -> list[str]:
    """The new files `may_add_files` let a task create. The keeper needs them by
    name, or the split's new file is never committed."""
    owned = {path.rstrip("/") for path in allowed}
    beside = _siblings(tree, owned)
    gitlinks = _gitlinks(tree)
    out = []
    for code, path, _source in _status_z(tree):
        if (not path or path.endswith("/") or path in gitlinks or code not in ("??", "A ", " A", "AM")):
            continue
        if _is_artefact(path):
            continue
        if str(pathlib.PurePosixPath(path).parent) in beside and path not in owned:
            out.append(path)
    return sorted(out)
