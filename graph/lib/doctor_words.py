"""Grep, sed and awk quote a PATTERN or PROGRAM, not a checkout path.

`grep -q '/health/ready'`, `sed -n '/health/ready/p'` and the multi-line
`awk '/regex/{...} ...'` a run stage pipes test output through all have the
same two-segment shape as a real checkout path — a leading slash, two or
more segments — so the doctor mistook a route or a test name for one. Only
the word each tool reads as its own pattern or program is blanked; `-f` and
`--file` name a real file to read one from and are left alone.

Split out of doctor.py at the 200-line cap (CLAUDE.md): the old name stays
the front door — `doctor.py` imports `operand_spans` from here.
"""

from __future__ import annotations

import re

_CMD_OPTS = {  # value-taking options: role "pat" blanks it, "file"/"" leave it
    "grep": {"-e": "pat", "--regexp": "pat", "-f": "file", "--file": "file",
             "-m": "", "-A": "", "-B": "", "-C": ""},
    "sed": {"-e": "pat", "--expression": "pat", "-f": "file", "--file": "file"},
    "awk": {"-F": "", "-v": "", "-f": "file"},
}


def operand_spans(gate: str) -> list[tuple[int, int]]:
    """Spans of each grep/sed/awk call's PATTERN/PROGRAM word, to blank —
    a tokenizer, not a regex: `--` ends options, a value-taking option eats
    the next word (or its attached `-m1`/`--file=X` form), and the first
    word left over is the operand unless an option already supplied one.

    A tool name counts only in shell command position — the first word of
    a simple command — so a pattern or file argument that happens to spell
    `sed` or `awk` (`grep -q sed file`) is never reparsed as a command. A
    match inside a still-open quote is rejected outright: a newline (or
    `;`/`&`/`|`/`(`/`{`) quoted as part of someone's pattern is not a real
    command boundary, however command-start it looks from the outside."""
    spans = []
    quoted = _quoted_spans(gate)
    for call in re.finditer(r"\b(?:[ef]?grep|sed|awk)\b", gate):
        if any(q0 < call.start() < q1 for q0, q1 in quoted):
            continue
        if not _at_cmd_start(gate, call.start()):
            continue
        opts = _CMD_OPTS["grep" if call.group().endswith("grep") else call.group()]
        pos, ended, given, first = call.end(), False, False, None
        while True:
            word = _word(gate, pos)
            if word is None:
                break
            start, end = word
            text = gate[start + 1:end - 1] if gate[start] in "'\"" else gate[start:end]
            pos = end
            if not ended and text == "--":
                ended = True
                continue
            if not ended and text != "-" and text.startswith("-"):
                opt, eq, rest = (text.partition("=") if text[1:2] == "-"
                                 else (text[:2], "", text[2:]))
                role, arg = opts.get(opt), None
                if role is not None:
                    if eq or rest:
                        arg = (start + len(opt) + (1 if eq else 0), end)
                    else:
                        arg = _word(gate, pos)
                        pos = arg[1] if arg else pos
                if arg:
                    if role == "pat":
                        spans.append(arg)
                    given = given or role in ("pat", "file")
                continue
            first = first or word
        if not given and first:
            spans.append(first)
    return spans


# ponytail: quotes are tracked without command substitution or escapes outside quotes —
# a tool call inside "$(...)" is not seen and an unquoted \' opens a quote; both only
# cost an advisory complaint on the board, none stands in the live backlog. A real shell
# lexer is the upgrade if a card ever needs them.
def _quoted_spans(s: str) -> list[tuple[int, int]]:
    """Spans (open-quote index, close-quote index) of every quoted region
    in the gate, one pass, real shell rules: a backslash escapes the next
    character inside double quotes, nothing escapes inside single quotes.
    An unterminated quote runs to the end of the string.

    Considered `shlex.shlex(s, posix=True, punctuation_chars=True)` first
    (ponytail rung 3) — it tokenizes words but not quote-interior character
    spans, and recovering spans from it needs as much bookkeeping as this
    loop, so a direct scan wins on code size."""
    spans, i, n = [], 0, len(s)
    while i < n:
        q = s[i]
        if q in "'\"":
            start = i
            i += 1
            while i < n and s[i] != q:
                i += 2 if q == '"' and s[i] == "\\" and i + 1 < n else 1
            spans.append((start, i))
            i += 1
        else:
            i += 1
    return spans


def _at_cmd_start(s: str, i: int) -> bool:
    """Whether i is the first word of a shell simple command: the start,
    or after `;`, `&`, `|`, `(`, `{`, or a newline — skipping back over
    spaces and the backslash-newline continuations that join lines rather
    than separate commands."""
    while i > 0:
        if s[i - 1] in " \t":
            i -= 1
        elif s[i - 1] == "\n" and i > 1 and s[i - 2] == "\\":
            i -= 2
        else:
            break
    # ponytail: exactly the boundary set the doctor's rule names; a wrapper
    # word (`timeout`, `xargs`, `if`, `!`) or `/usr/bin/grep` still reads as
    # command position elsewhere and is missed, same as a continuation
    # spliced mid-word rather than between words — widen here if a real
    # gate ever needs either.
    return i == 0 or s[i - 1] in ";&|({\n"


def _word(s: str, pos: int):
    n = len(s)
    while pos < n:
        if s[pos] in " \t":
            pos += 1
        elif s[pos] == "\\" and pos + 1 < n and s[pos + 1] == "\n":
            pos += 2
        else:
            break
    if pos >= n or s[pos] in ";|&\n":
        return None
    if s[pos] in "'\"":
        end = s.find(s[pos], pos + 1)
        return (pos, end + 1) if end != -1 else (pos, n)
    end = pos
    while end < n and s[end] not in " \t;|&\n":
        end += 1
    return (pos, end)
