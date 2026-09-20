"""Two checks on a gate's own text, run before any contract is stored.

`has_pipefail_header` -- whether the gate's own first line turns on -e and
pipefail. A multiline gate without `-e` reports only its last line: every
earlier failing leg is silently forgiven (a lesson: "Running a loop
unattended"). The planner kept writing multi-step gates as a same-line
`set -o pipefail; (a) && (b) && (c ; d)` chain or bare newline-separated
commands instead, and the slicer's own reviewer refused them before a
person decided (2026-09-03).

`pins_a_count` -- whether the gate pins a test runner's EXPECTED to a
literal, to `len(...)`, or to a value read from HEAD. A lesson: "the
triage runner counts its own test cases (EXPECTED), so a card gate that
restated the count -- first as a literal, then as len(MODULES) -- broke
the moment a module held two tests, and the keeper re-runs kept gates on
the combined tree, so a wrong clause on a done card stops its siblings
too" (2026-09-03, two data sweeps in one night). A runner that declares
a bare `EXPECTED` (the triage runner today; the verifier's is named
EXPECTED_TESTS and the journal's declares neither) uses it as the count of
test cases it collects, so the check is scoped to gates that mention a
`run_all` module, never to every EXPECTED-named value anywhere. A gate that reads run_all.py with
`ast` never writes the word EXPECTED next to its comparison: it binds the
looked-up node to a short alias first (`e=A(R,'EXPECTED')`), maybe
unwraps it once more (`expected=e.value`), and pins two statements later
(`e.value==14`) -- the recorded case this module's own tests replay.
`pins_a_count` traces that binding instead of matching the word EXPECTED
alone, reads the comparison in either order and with either operand
optionally parenthesised, and walks the gate in statement order so a
name's alias status is judged as it stood at each comparison, not from a
position-blind summary of the whole text -- an alias bound only after a
comparison never taints it, and a comparison made before a later,
unrelated reassignment still does. A second, symmetric trace catches a
value read from `git show HEAD:` / `HEAD:`: that form was blessed once,
as "HEAD's value plus this card's own tests", and it broke the same day
it landed -- the keeper re-runs a gate after committing the work, so by
the second run HEAD already holds what the gate calls new, and the
comparison is never true again. A third, independent check catches the
same pin spelled as a shell search instead of a Python comparison: `grep
-q '^EXPECTED = 15$' run_all.py` demands the source line read exactly
that, which pins the count just as hard.

Both rules live here, in drive/lib, so any reader can share them the way
`is_live` and `gate_files` are shared -- never re-derived at each call site.
"""

from __future__ import annotations

import re

_HEADER = "set -e -o pipefail"


def has_pipefail_header(gate: str) -> bool:
    """Whether the gate's own first line -- the whole gate, if it holds no
    newline -- is exactly `set -e -o pipefail`, trailing whitespace only
    stripped. No blank or comment line before it, no split across two
    lines, no reordered flags: the prompt asks for this exact spelling on
    the exact first line, so the parser demands the same text, not a
    tolerant reading of it."""
    return gate.partition("\n")[0].rstrip() == _HEADER


_COUNT = r"-?\d+\b|len\((?:[^()]|\([^()]*\))*\)"
_DIRECT = r"""(?:\bEXPECTED\b|\bexpected\.value\b|\["EXPECTED"\]|\['EXPECTED'\])"""
# A whole statement (already split on `;`/newline) that is entirely
# `name=rhs`, so `a==b` is never read as an assignment.
_ASSIGN_STMT = re.compile(r"\s*([A-Za-z_]\w*)\s*=(?!=)(.*)", re.DOTALL)
# `python3 -c "PROGRAM"` (or single-quoted) glues PROGRAM's own first
# statement to the `-c "` that precedes it, so a leading `name=...` inside
# never matches at the true start of a statement. Unwrapped into its own
# `;`-delimited text before anything is split.
_C_PROGRAM = re.compile(r"-c\s*(\"[^\"]*\"|'[^']*')")
# A grep pattern demanding the runner's own source line read exactly
# `EXPECTED = <int>` pins the count the same way a `==` comparison does,
# whether spelled with regex anchors or a fixed string (-F).
_GREP_PIN = re.compile(r"\bEXPECTED\s*=\s*(-?\d+)")


def _wrap(pattern: str) -> str:
    """`pattern` optionally parenthesised. `pattern` may itself be a bare
    `A|B` alternation, so the parenthesised branch must group it first --
    `\\(A|B\\)` would parenthesise only the B branch."""
    return rf"(?:\((?:{pattern})\)|(?:{pattern}))"


# ponytail: alias-tracing ceiling -- only a top-level `name=rhs` statement
# is read (including one inside a single, unescaped `-c "..."` / `-c
# '...'` program, unwrapped before splitting); a walrus (`:=`) or a name
# bound only inside a comprehension's own scope hides the lookup, and
# tainting is substring-based, so a container merely mentioning
# 'EXPECTED' or 'HEAD:' taints the whole name it is assigned to; a
# chained `a=b=A(R,'EXPECTED')` taints only the outer name, `len(...)`
# balances one level of nested parens, not more, and the grep-pin check
# is a plain `EXPECTED = <int>` substring search, not scoped to text
# actually inside a grep argument. Upgrade: a real ast walk of the gate's
# embedded Python, if this keeps missing a recorded case.
def pins_a_count(gate: str) -> str | None:
    """The offending fragment when the gate text pins a runner's EXPECTED,
    else None. Only run at all when the gate mentions a runner module
    (`run_all` -- triage, verifier, journal all declare EXPECTED the same
    way); a gate comparing an unrelated EXPECTED to anything is always
    fine. Three independent forms are refused: (1) EXPECTED -- spelled
    `EXPECTED`, `expected.value`, `["EXPECTED"]`, `['EXPECTED']`, or an
    alias bound from one of those earlier in the same statement sequence
    -- compared, in either order and with either side optionally
    parenthesised, to an integer literal, to a `len(...)` call, or to a
    value read from `git show HEAD:` / `HEAD:` (traced by alias the same
    way); (2) that same comparison written as a grep search over the
    runner's own source (`grep -q '^EXPECTED = 15$' run_all.py`); the
    only fine comparison is against what the runner itself collects
    (`countTestCases()`, `run_all.EXPECTED`) -- a value read from HEAD
    looked fine when it landed and failed on the very next re-run,
    because the keeper re-runs a gate after committing the work, so HEAD
    already holds what the gate calls new. Statements are walked in
    order, and a name's taint is judged as it stood at each comparison:
    `e=A(R,'EXPECTED'); assert e.value==15; e=42` is still a pin (the
    comparison came first); `e=99; assert e.value==15;
    e=A(R,'EXPECTED')` is not (the alias is bound only after). An
    assignment's own right-hand side is checked too (`pinned = EXPECTED
    == 15`)."""
    if "run_all" not in gate:
        return None
    grep_hit = _GREP_PIN.search(gate)
    if grep_hit:
        return grep_hit.group(1)
    gate = _C_PROGRAM.sub(lambda match: ";" + match.group(1)[1:-1] + ";", gate)
    known: set[str] = set()
    from_head: set[str] = set()
    for statement in re.split(r"[;\n]", gate):
        names = _DIRECT
        if known:
            alternatives = "|".join(re.escape(alias) for alias in sorted(known))
            names = rf"(?:{_DIRECT}|\b(?:{alternatives})\b(?:\.value\b)?)"
        count = _COUNT
        if from_head:
            head = "|".join(re.escape(alias) for alias in sorted(from_head))
            count = rf"(?:{_COUNT}|\b(?:{head})\b(?:\.value\b|\[[^\]]*\])?)"
        names, count = _wrap(names), _wrap(count)
        hit = re.search(rf"{names}\s*==\s*(?P<rhs>{count})|(?P<lhs>{count})\s*==\s*{names}",
                        statement)
        if hit:
            return hit.group("rhs") or hit.group("lhs")
        assigned = _ASSIGN_STMT.fullmatch(statement)
        if not assigned:
            continue
        name, rhs = assigned.group(1), assigned.group(2)
        if re.search(r"\bEXPECTED\b", rhs) or any(
                re.search(rf"\b{re.escape(alias)}\b", rhs) for alias in known):
            known.add(name)
        else:
            known.discard(name)
        if "HEAD:" in rhs or any(
                re.search(rf"\b{re.escape(alias)}\b", rhs) for alias in from_head):
            from_head.add(name)
        else:
            from_head.discard(name)
    return None
