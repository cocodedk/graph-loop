"""A diff too long for the reviewer's input, cut down to fit without cutting any file's section in the middle:
a stat line for every file, the whole sections of the smallest files that fit, and a list of the rest."""

from __future__ import annotations

import re

NOT_SHOWN = "These files were too large to include; you can read them in your worktree."
Section = tuple[str, str]   # a file's name and its text in the diff


def sections(diff: str) -> list[Section]:
    """One section per `diff --git` line, text before the first joined to it; no such line, one section."""
    parts = re.split(r"(?m)^(?=diff --git )", diff)
    if len(parts) == 1:
        return [("(the diff)", diff)] if diff else []
    parts[1] = parts[0] + parts[1]
    return [(_name(part), part) for part in parts[1:]]


def _name(part: str) -> str:
    """The file's new path: from `rename to`, a quoted header, a header whose two paths are equal (a path may
    hold ` b/`, so the header is cut in the middle), then `+++ b/`; git's escapes in a quoted path stay as written."""
    lines = part[part.index("diff --git "):].split("\n")
    rest = lines[0][len("diff --git "):]
    renamed = next((line[len("rename to "):] for line in lines if line.startswith("rename to ")), None)
    quoted = re.fullmatch(r'(?:"a/.*"|a/.*?) "b/(.*)"', rest)
    size = (len(rest) - 5) // 2
    if renamed:
        return renamed.strip('"')
    if quoted:
        return quoted.group(1)
    if len(rest) % 2 == 1 and size > 0 and rest[2:2 + size] == rest[-size:]:
        return rest[-size:]
    return next((line[len("+++ b/"):] for line in lines if line.startswith("+++ b/")), rest.rsplit(" b/", 1)[-1])


def counts(section: str) -> tuple[int, int]:
    """Lines added and removed: only the lines after the first hunk header count."""
    lines = section.split("\n")
    body = lines[next((n for n, line in enumerate(lines) if line.startswith("@@")), len(lines)) + 1:]
    return (sum(line.startswith("+") for line in body), sum(line.startswith("-") for line in body))


def _stat(one: Section) -> str:
    (added, removed) = counts(one[1])
    return f"{one[0]} | +{added} -{removed}\n"


def _listing(hidden: list[Section]) -> str:
    return "" if not hidden else (
        "## Not shown\n\n" + "".join(f"{name} ({len(text)} characters)\n" for (name, text) in hidden)
        + f"\n{NOT_SHOWN}\n")


def _layout(stat: str, shown: list[str], listing: str) -> str:
    return (f"## Changed files\n\n{stat}\n" + ("## Diff of the files shown\n\n" + "".join(shown) + "\n" if shown else "")
            + listing)


def _stat_fitted(files: list[Section], listing: str, budget: int) -> str:
    """The stat keeps the files with the most lines changed, as many as fit beside `listing`, then a line
    for the rest."""
    used = len(_layout("", [], listing))
    kept = ""
    for (n, one) in enumerate(sorted(files, key=lambda one: (-sum(counts(one[1])), one[0]))):
        left = len(files) - n - 1
        if used + len(_stat(one)) + (len(f"... and {left} more files\n") if left else 0) > budget:
            break
        used += len(_stat(one))
        kept += _stat(one)
    left = len(files) - kept.count("\n")
    return _layout(kept + (f"... and {left} more files\n" if left else ""), [], listing)


def _squeezed(files: list[Section], budget: int) -> str:
    """The never-cut parts alone are over the budget: the stat is shortened first; only when that alone does
    not fit does the list of files not shown become one line."""
    by_size = sorted(files, key=lambda one: (len(one[1]), one[0]))
    first = _stat_fitted(files, _listing(by_size), budget)
    return first if len(first) <= budget else _stat_fitted(
        files, f"## Not shown\n\n{len(files)} files not shown\n", budget)


def shorten(diff: str, budget: int) -> str:
    """`diff` as a text of at most `budget` characters, or the smallest it can be when even that is over."""
    files = sections(diff)
    stat = "".join(_stat(one) for one in files)
    by_size = sorted(files, key=lambda one: (len(one[1]), one[0]))
    if len(_layout(stat, [], _listing(by_size))) > budget:
        return _squeezed(files, budget)
    shown: list[str] = []
    for (n, (_, text)) in enumerate(by_size):
        whole = text if text.endswith("\n") else text + "\n"
        # ponytail: laid out again per file, fine for the few hundred that fit; a running total is the upgrade
        if len(_layout(stat, shown + [whole], _listing(by_size[n + 1:]))) > budget:
            break
        shown.append(whole)
    return _layout(stat, shown, _listing(by_size[len(shown):]))
