"""Which programs a gate runs, read from the gate's own text.

The builder's shell used to be a fixed list with `python3` and one linter in it,
so the loop could PLAN a project in any language and BUILD only a Python one:
the first real campaign wrote Java cards, and every one of them parked because
its builder could not run `javac` (2026-09-18).

Adding `javac` to the list would move the wall, not remove it. The card already
says what proves it — its gate — and that gate is written by the slicer, refused
or accepted by an independent reviewer before any build, and then RUN as the
verdict. So the programs it names are already declared, already reviewed, and
already going to execute.

This file only READS them. What may then be granted is `tools.code_shell`'s
question, and it is a real widening: the gate runs one fixed command line, a
grant is every invocation of the name. The floor over that reading is
`tools.NEVER_WILDCARD`.

What is NOT derived from the card stays fixed: reading and version control,
which every card needs whatever it is written in, and the denies, which no
gate can talk its way past.
"""

from __future__ import annotations

import re
import shlex

# Where one command ends and the next begins. A token that follows one of these
# is a program; anything else is an argument to the program before it.
BREAKS = frozenset({"&&", "||", "|", ";", "&", "(", ")", "{", "}", "!", "|&"})
# Shell built-ins and keywords: the shell runs them, so they are not programs to
# be granted, and `then`/`do`/`else` would otherwise be read as command names.
BUILTIN = frozenset({
    "if", "then", "elif", "else", "fi", "for", "while", "until", "do", "done",
    "case", "esac", "in", "function", "select", "time", "coproc",
    "set", "cd", "export", "unset", "local", "readonly", "shift", "return",
    "exit", "eval", "exec", "source", ".", "trap", "wait", "true", "false",
    "echo", "printf", "read", "test", "[", "[[", "]]", "]",
})
# A command substitution runs its own commands, and the gate's most-used program
# hides in one: every Java gate the first campaign wrote opened
# `WORK="$(mktemp -d)"`, so `mktemp` never once stood in command position. The
# innermost pair matches first, which is what lets the layers peel.
SUBSTITUTION = re.compile(r"\$\((?P<inside>[^()]*)\)|`(?P<tick>[^`]*)`")
# What may be granted: a name the gate literally spelled. Never `$CMD`, never a
# quote or a fragment of syntax a reading of the text left behind.
NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*")
# `python3 - <<'PY'` opens a body that is data, not commands: the shell runs
# none of it, and its terminator is a word.
HEREDOC = re.compile(r"""<<-?\s*(['"]?)(?P<word>[A-Za-z_][A-Za-z0-9_]*)\1""")


def programs(gate: str) -> list[str]:
    """Every program this gate invokes: its own commands in the order it names
    them, then the ones inside its command substitutions.

    Read the way a shell reads it: the first word of the whole text, and the
    first word after every separator. A `VAR=value` prefix is an assignment,
    not a program, so the word after it is the one that runs.

    A gate this cannot parse yields nothing rather than guessing. The builder
    then gets the fixed base alone and the card fails honestly on a missing
    tool, which is a story somebody can read — a guessed grant is not.
    """
    found: list[str] = []
    for text in _layers(gate):
        for name in _commanded(text):
            if name not in found:
                found.append(name)
    return found


def _layers(gate: str) -> list[str]:
    """The gate with its command substitutions blanked, then their contents.

    Peeled innermost first, so a substitution's own commands are read as
    commands and the text around it keeps the shape a shell would see: with
    `$(mktemp -d)` blanked, `WORK=" "` is still the assignment it was.
    """
    layers, text = [], gate
    while True:
        insides = [found["inside"] if found["inside"] is not None else found["tick"]
                   for found in SUBSTITUTION.finditer(text)]
        layers.append(SUBSTITUTION.sub(" ", text))
        if not insides:
            return layers
        text = "\n".join(insides)


def _lines(text: str) -> list[str]:
    """One line per command, heredoc bodies removed.

    Line by line, because `shlex` drops newlines and a gate's
    `set -e -o pipefail` header would otherwise swallow the line below it. But
    a line is not always a command: the campaign's javac lines wrap, and a
    trailing backslash escapes nothing at the end of a string, so `shlex`
    raised and the line holding `javac` was dropped whole. Joining first is
    what the shell does anyway.
    """
    kept, ending = [], ""
    for line in text.replace("\\\n", " ").splitlines():
        if ending:
            ending = "" if line.strip() == ending else ending
            continue
        kept.append(line)
        opened = HEREDOC.search(line)
        if opened:
            ending = opened["word"]
    return kept


def _commanded(text: str) -> list[str]:
    """The program of every command in one layer of text."""
    found: list[str] = []
    for line in _lines(text):
        try:
            words = shlex.split(line, comments=True)
        except ValueError:          # an unbalanced quote: no reading to be had
            continue
        starting = True
        for word in words:
            if word in BREAKS:
                starting = True
                continue
            if not starting:
                continue
            if "=" in word and word.split("=", 1)[0].isidentifier():
                continue            # an assignment prefix; the next word runs
            starting = False
            name = word.rsplit("/", 1)[-1]      # ./run.sh and /usr/bin/javac
            if NAME.fullmatch(name) and name not in BUILTIN and name not in found:
                found.append(name)
    return found
