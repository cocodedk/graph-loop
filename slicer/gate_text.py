"""Shell text primitives for gate_output.py: where a quote or heredoc body
ends, and what a `tee` operand list or a nested $(...)/`...` contains.

Split from gate_output.py at the 200-line cap: everything here is text
scanning only -- what target is safe to write is gate_output.py's own job.
"""

from __future__ import annotations

import re

_HEREDOC = re.compile(r"<<-?\s*([\"']?)(\w+)\1")


def skip_quote(text: str, i: int) -> int:
    """Index right after the quote starting at text[i] (escape-aware for
    double quotes -- a run of backslashes right before the candidate quote
    escapes it only when the run is ODD, since backslashes pair off in
    pairs of two; `"\\\\"` is one escaped backslash and closes normally.
    Single quotes have no escaping in real shell)."""
    ch, n = text[i], len(text)
    j = i + 1
    while j < n:
        if text[j] == ch:
            k = j - 1
            backslashes = 0
            while k >= i and text[k] == "\\":
                backslashes += 1
                k -= 1
            if ch != '"' or backslashes % 2 == 0:
                break
        j += 1
    return min(j + 1, n)


def _token(text: str, i: int) -> tuple[str, int]:
    """One word starting at text[i], quote-aware: a quoted span stays part
    of the word whole even if it holds a `)`, `|`, `&`, or `;` -- e.g.
    `"$(mktemp)"` is one word despite its own `)`. Stops at the first
    unquoted whitespace or one of those four characters, e.g. so `2>&1)`
    reads its word as "1", not "1)" swallowing the subshell's own close.
    Returns (word, index right after it)."""
    start, n = i, len(text)
    while i < n and text[i] not in " \t\n|&;)":
        i = skip_quote(text, i) if text[i] in "'\"" else i + 1
    return text[start:i], i


def tee_targets(text: str, i: int) -> list[str]:
    """Every file operand `tee` is given starting at text[i] -- each found
    with `_token`, so the argument list itself ends at the first
    character, unquoted, that is whitespace-separated stop punctuation
    (|, &, ;, )) -- with any flag (`-a`) dropped."""
    targets, n = [], len(text)
    while i < n and text[i] in " \t":
        i += 1
    while i < n and text[i] not in "|&;)\n":
        token, i = _token(text, i)
        targets.append(token)
        while i < n and text[i] in " \t":
            i += 1
    return [t for t in targets if not t.startswith("-")]


def redirect_target(text: str, i: int) -> str:
    """The one word a `>`/`>>`/`>|`/`>&` redirect writes to, starting at
    text[i] (leading whitespace skipped) -- found the same quote- and
    metacharacter-aware way as a `tee` operand, via `_token`."""
    n = len(text)
    while i < n and text[i] in " \t":
        i += 1
    return _token(text, i)[0]


def quoted_spans(text: str) -> list[tuple[int, int, bool]]:
    """(start, end, live) for every quoted string, `#` comment, and heredoc
    BODY -- a heredoc's own header line is live shell and never masked;
    only the body, from the line after it to the terminator, is. A `#`
    starts a comment (masked, never live -- bash never expands anything in
    one) only at the start of a word: text start, or right after
    whitespace or one of `;|&(){}`, so `foo#bar` stays one literal word.
    live is True for a double-quoted string or an unquoted-delimiter
    heredoc body, where bash still expands a nested $(...) or `...`; False
    for single quotes, a comment, or a quoted delimiter (`<<'EOF'`), which
    bash never expands at all."""
    spans, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch in "'\"":
            j = skip_quote(text, i)
            spans.append((i, j, ch == '"'))
            i = j
            continue
        if ch == "#" and (i == 0 or text[i - 1] in " \t\n;|&(){}"):
            j = text.find("\n", i)
            j = n if j < 0 else j
            spans.append((i, j, False))
            i = j
            continue
        if text[i:i + 2] == "<<":
            m = _HEREDOC.match(text, i)
            if m:
                body = text.find("\n", m.end())
                body = m.end() if body < 0 else body + 1
                end = text.find("\n" + m.group(2), body)
                end = n if end < 0 else end
                spans.append((body, end, not m.group(1)))
                i = end
                continue
        i += 1
    return spans


def nested(text: str, start: int, end: int) -> list[str]:
    """Every $(...) or `...` command substitution's own inner text, found
    inside text[start:end] -- bash still executes these even though the
    span around them (a double-quoted string, an unquoted heredoc's own
    body) is not top-level shell. Parens are balanced quote-aware, so a
    `)` written inside a nested quote -- `$(echo ')' > x)` -- never ends
    the substitution early. A `$(` with no balanced `)` before `end` is a
    quote this small tokenizer mis-bounded, not a real substitution, and
    is skipped rather than scanned as a truncated fragment."""
    out, i = [], start
    while i < end:
        if text[i] == "`":
            j = text.find("`", i + 1, end)
            if j < 0:
                break
            out.append(text[i + 1:j])
            i = j + 1
            continue
        if text[i:i + 2] == "$(":
            depth, j = 1, i + 2
            while j < end and depth:
                if text[j] in "'\"":
                    j = skip_quote(text, j)
                    continue
                depth += {"(": 1, ")": -1}.get(text[j], 0)
                j += 1
            if depth == 0:
                out.append(text[i + 2:j - 1])
            i = j
            continue
        i += 1
    return out
