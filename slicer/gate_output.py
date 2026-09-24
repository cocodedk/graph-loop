"""Refuse gate output without an owner: the driver or an EXIT cleanup trap.

The driver owns `$TMPDIR` and bare `mktemp` output. A gate can also own a
probe beside the project's tests by removing that same target on EXIT.
Other repository output is refused before the driver's lane guard sees it.
Quote, comment, heredoc and nested-substitution scanning lives in gate_text.py.

The existing scratch rules stay: variables must be assigned only from bare
`mktemp` or `mktemp -d`; directory suffixes must not escape via `..`.
Assigning TMPDIR revokes that trust. Single-quoted variables are literals.
Every tee operand and redirect target is checked; descriptor duplication
writes no file. Live nested substitutions are scanned recursively.
"""

# ponytail: this is a scanner over masked shell text, not a bash parser --
# a gate can still hide a sink behind eval, printf %s -v, exec redirection,
# or a helper script it shells out to. Upgrade path: run the gate under a
# read-only bind mount of the repository; the driver's own lane guard
# (loop_judge_retry.gate_left_its_lane) remains the guard of record.

from __future__ import annotations

import re
from os.path import normpath

from gate_text import nested, quoted_spans, redirect_target, tee_targets

_MKTEMP_CALL = r"\$\(\s*mktemp\b(?P<args>[^)]*)\)"
# The quote is optional and must match: without it `WORK="$(mktemp -d)"`, which is what the slicer writes, fell through to the bare-assignment scan below and its gate was refused (2026-09-18; the case is in test_contracts_gate_output).
_MKTEMP = re.compile(r"\b(?P<name>[A-Za-z_]\w*)=(?P<quote>[\"']?)" + _MKTEMP_CALL + r"(?P=quote)")
_MKTEMP_INLINE = re.compile("^" + _MKTEMP_CALL + "$")
_ASSIGN = re.compile(r"\b([A-Za-z_]\w*)=")
_SINK = re.compile(
    r"(?P<amp>(?<![->])\d*>&(?!=))"
    r"|(?P<redir>(?<![->])\d*(?:>\||>{1,2})(?!=))"
    r"|\btee\b")
_VAR = re.compile(r"\$\{?([A-Za-z_]\w*)\}?(.*)$")
_KEYWORD_START = re.compile(r"\b(?:then|do|else)\s*$")


def _trusted_mktemp(args: str | None) -> bool:
    """Whether a $(mktemp ...) call takes its root from $TMPDIR, which the
    driver points at the gate's own home and removes afterwards: the bare
    `mktemp` (file) and `mktemp -d` (directory). Any argument (`-p /tmp`, a
    `./gate.XXXXXX` template) names a root the driver does not own; the
    caller separately checks that this gate never assigns TMPDIR."""
    return (args or "").split() in ([], ["-d"])


def _escapes(suffix: str) -> bool:
    """Whether a directory-variable sink's own suffix carries a `..`
    segment that walks back out of the mktemp'd directory, e.g.
    `$d/../../repo-path` escaping into the repository it was meant to
    stay clear of."""
    return ".." in suffix.split("/")


def _rooted_safely(bare: str) -> bool:
    """Whether bare, path-normalized (no ../ tricks), is /dev/null -- the one
    absolute path a gate may name, because it keeps nothing. Normalizing
    first refuses `/dev/null/../repo.out`, while still tolerating trailing
    shell punctuation attached with no space, e.g. `/dev/null)` from `(... >
    /dev/null)`, since normpath does not touch a non-path character."""
    return normpath(bare).startswith("/dev/null")


def _command_position(text: str, pos: int) -> bool:
    """Whether text[pos] begins a new command -- start of text, start of a
    line, or right after |, &&, ||, ;, (, {, or then/do/else -- so a plain
    word argument (`grep -q tee app.py`) is never read as an invocation."""
    stripped = text[:pos].rstrip(" \t")
    if not stripped or stripped.endswith("\n"):
        return True
    return stripped.endswith(("|", "&&", ";", "(", "{")) or bool(
        _KEYWORD_START.search(stripped))


def _outside(pos: int, spans: list[tuple[int, int, bool]]) -> bool:
    return not any(start <= pos < end for start, end, _ in spans)


def _mktemp_names(text: str, spans: list[tuple[int, int, bool]]) -> dict[str, bool]:
    """The names this gate may write through, mapped to whether each is a
    directory: `TMPDIR` itself, which the driver owns and removes, and every
    name assigned from a trusted `$(mktemp)` / `$(mktemp -d)` call, which
    follows it. Excludes a name that has any OTHER assignment anywhere in
    the gate (a second, different assignment to the same name is exactly
    the `OUT=zone-claim.out; tee "$OUT"` bypass this exists to refuse) or
    any mktemp call not in one of the two trusted forms. A gate that assigns
    TMPDIR in ANY form gets none of them, the driver owning where none of
    them land -- so `TMPDIR` in the result is also the caller's answer to
    "does this gate leave TMPDIR alone"."""
    dirs: dict[str, bool] = {}
    bad = set()
    for match in _MKTEMP.finditer(text):
        if not _outside(match.start(), spans):
            continue
        name, args = match["name"], match["args"]
        if _trusted_mktemp(args):
            dirs.setdefault(name, (args or "").split() == ["-d"])
        else:
            bad.add(name)
    other = set()
    for match in _ASSIGN.finditer(text):
        if _outside(match.start(), spans) and not _MKTEMP.match(text, match.start()):
            other.add(match.group(1))
    if "TMPDIR" in other or "TMPDIR" in bad or "TMPDIR" in dirs:
        # ANY assignment of TMPDIR, its own mktemp call included, moves the
        # root the driver owns: `TMPDIR=$(mktemp -d ./leak.XXXXXX)` put every
        # "$TMPDIR/..." write below it into the repository (Codex)
        return {}
    return {name: is_dir for name, is_dir in dirs.items()
            if name not in other and name not in bad} | {"TMPDIR": True}


def _targets(match: re.Match) -> list[str]:
    """The file(s) one `_SINK` match writes. The "amp" alternative is
    `>&word`'s own target -- real only when word is not purely a
    descriptor number or `-`, which duplicate a stream and write nothing.
    "redir" is a plain `>`/`>>`/`>|` target, always real -- both found via
    `redirect_target`'s quote-aware scan, since a regex capture (`\\S+`)
    does not stop at an unquoted `)`, reading `2>&1)` as target "1)" and
    missing the digit it actually is. `tee` can be given several (each
    its own write), found the same way via `tee_targets`."""
    if match.group("amp") is not None:
        word = redirect_target(match.string, match.end())
        return [] if re.fullmatch(r"\d+|-", word) else [word]
    if match.group("redir") is not None:
        return [redirect_target(match.string, match.end())]
    return tee_targets(match.string, match.end())


def _exit_cleanup_targets(text: str, spans: list[tuple[int, int, bool]]) -> set[str]:
    """Exact targets of `rm [-f] [--] target` commands in a quoted EXIT trap."""
    targets = set()
    for match in re.finditer(r"\btrap\s+(['\"])(.*?)\1\s+EXIT(?=\s|[;&)]|$)", text):
        if not _outside(match.start(), spans) or not _command_position(text, match.start()):
            continue
        for command in re.split(r";|&&|\|\|", match.group(2)):
            command = command.strip()
            remove = re.match(r"rm\s+(?:-f\s+)?(?:--\s+)?", command)
            if remove:
                target = redirect_target(command, remove.end())
                if target and command[remove.end():].strip() == target:
                    targets.add(target.strip('"'))
    return targets


def _sinks(text: str, safe: dict[str, bool]) -> list[str]:
    """Sink targets in `text`'s own top-level shell, plus -- recursively --
    every command substitution bash still executes inside a live span."""
    spans = quoted_spans(text)
    cleaned = _exit_cleanup_targets(text, spans)
    found = []
    for match in _SINK.finditer(text):
        if not _outside(match.start(), spans):
            continue
        is_tee = match.group("amp") is None and match.group("redir") is None
        if is_tee and not _command_position(text, match.start()):
            continue
        for target in _targets(match):
            literal = target[:1] == "'" and target[-1:] == "'"
            bare = target.strip("'\"")
            if target.strip('"') in cleaned or _rooted_safely(bare):
                continue
            if not literal:
                call = _MKTEMP_INLINE.match(bare)
                # "TMPDIR" in safe is this gate leaving TMPDIR alone; an
                # inline call in a gate that poisons it is no safer than an
                # assigned one
                if call and "TMPDIR" in safe and _trusted_mktemp(call["args"]):
                    continue
            if not re.search(r"[A-Za-z0-9]", bare):
                continue
            if not literal:
                var = _VAR.match(bare)
                if var and var.group(1) in safe and (
                        not var.group(2) or
                        (safe[var.group(1)] and var.group(2).startswith("/")
                         and not _escapes(var.group(2)))):
                    continue
            found.append(target)
    for start, end, live in spans:
        if live:
            for inner in nested(text, start, end):
                found.extend(_sinks(inner, safe))
    return found


def unsafe_gate_sinks(gate: str) -> list[str]:
    """Every `>`/`>>`/`>|`/`>&`/`tee` target this gate's own shell text
    writes -- including inside a nested $(...)/`...` bash still executes --
    that is not `/dev/null`, the driver-owned `$TMPDIR`, a bare unquoted
    `$(mktemp)`/`$(mktemp -d)` call, or a variable assigned only from one
    (a directory only as `$NAME/...`, and never with a `..` segment in the
    suffix), or a target removed by this shell's EXIT trap. Assigning
    TMPDIR itself revokes the driver-owned scratch trust."""
    return _sinks(gate, _mktemp_names(gate, quoted_spans(gate)))
