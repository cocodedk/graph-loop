"""Whether a gate's own output lands inside the repository it judges.

A gate that tees or redirects into a bare filename writes into the tree it
is meant to judge -- the fault that cost a 20-minute build (2026-09-03)
before the drive loop's own lane guard caught it (`loop_judge_retry.py`,
`gate_left_its_lane`), after the build was already paid for. The slicer
refuses what the driver would refuse, before anything is spent.

Scratch has an owner, and the owner is the driver: `run_gate` gives a gate
a home, points `$TMPDIR` at it and removes it when the gate ends. What a
gate wrote to the host's own `/tmp` stayed instead, and /tmp filling on
2026-09-03 killed every process on the host, so literal `/tmp` is refused
here too.

Text scanning (quotes, comments, heredoc bodies, tee's operand list, a
nested $(...)/`...`) lives in gate_text.py, split out at the 200-line cap.
The rules this module applies to what it finds, after six Codex review
rounds: a target is safe only as `/dev/null`, `$TMPDIR`/`${TMPDIR}`, a
bare unquoted `$(mktemp)` / `$(mktemp -d)` call (both follow `$TMPDIR`,
falling back to /tmp only in a shell that has none, such as the builder's
own), or a `$VAR` this same gate assigns, alone, from one of those two
calls (a directory only as `$NAME/sub`, and never with a `..` segment
walking back out). A gate that assigns `TMPDIR`, in any form, is trusted
with none of it: `TMPDIR=. mktemp` and `TMPDIR=$(mktemp -d ./leak.XXXXXX)`
both steer the write into the repository. A single-quoted target (`'$OUT'`,
`'$(mktemp)'`) is literal text, never an expansion. `>&word` writes a real
file unless word is bare digits or `-` (a descriptor duplication, e.g.
`2>&1`); every operand `tee` is given is checked, not just its first, and
only when `tee` is itself in command position (never a plain word, as in
`grep -q tee app.py`). A substitution nested inside a live span (a
double-quoted string, an unquoted heredoc's body) is itself extracted and
scanned the same way, recursively.
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


def _sinks(text: str, safe: dict[str, bool]) -> list[str]:
    """Sink targets in `text`'s own top-level shell, plus -- recursively --
    every command substitution bash still executes inside a live span."""
    spans = quoted_spans(text)
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
            if _rooted_safely(bare):
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
    suffix). A gate that assigns TMPDIR itself keeps none of that trust."""
    return _sinks(gate, _mktemp_names(gate, quoted_spans(gate)))
