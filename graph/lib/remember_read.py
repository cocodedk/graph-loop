"""What the command understands a memory note to be — and nothing else.

Three rounds of review found the same shape each time: a file spelled a little
differently from what was expected, written anyway, and something lost. So the
guessing stopped. A note is refreshed only when every line of a short list is
true of its raw BYTES, and anything else is left exactly as it is, counted, and
named. When in doubt, do not write.

The list, and it is the whole of it:

- valid UTF-8, and no byte-order mark;
- LF line endings only, nowhere a carriage return;
- front matter, delimited by plain `---` lines — an existing file is never
  GIVEN any, because without it nothing says whose note it is;
- every fenced block closed by the rule: the closing fence is the same
  character, at least as long as the opening one, with nothing after it but
  spaces or tabs. A non-breaking space does not close a fence.

Whether the front matter PARSES, and whether it names this card, is the next
question and `remember_front` answers it.
"""

from __future__ import annotations

import codecs
import re

FENCE = re.compile(r"^ {0,3}(?P<mark>`{3,}|~{3,})(?P<info>.*)$")
CLOSES = re.compile(r"^[ \t]*$")      # a closing fence carries spaces and tabs, nothing else
EDGE = "---\n"


def understood(raw: bytes) -> tuple[str, str]:
    """This note's text when the command fully understands the file, and why
    it does not when it does not. One of the two is always empty."""
    if raw.startswith(codecs.BOM_UTF8):
        return "", "it begins with a byte-order mark"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return "", "it is not UTF-8"
    if "\r" in text:
        return "", "it has carriage returns, and only LF line endings are read here"
    if split(text) is None:
        return "", ("it has no front matter between plain `---` lines, and an existing "
                    "note is never given any — without it nothing says whose note it is")
    if plain(text)[1]:
        return "", ("it has a fenced block that nothing closes by the fence rule, so "
                    "where a person's own text ends cannot be read")
    return text, ""


def split(text: str) -> tuple[str, str] | None:
    """(the front-matter block, both `---` lines and all, the body), or None
    when this is not a note with front matter. The block is returned as its own
    bytes, never rebuilt: rebuilding it is what dropped a delimiter's spacing."""
    if not text.startswith(EDGE):
        return None
    end = text.find("\n" + EDGE, len(EDGE) - 1)
    if end < 0:
        return None
    return text[:end + len(EDGE) + 1], text[end + len(EDGE) + 1:]


def front(text: str) -> str:
    """The YAML between the delimiters, for a text `split` accepts."""
    block = (split(text) or ("", ""))[0]
    return block[len(EDGE):len(block) - len(EDGE)]


def plain(text: str) -> tuple[list[tuple[int, str]], bool]:
    """Every line that is not inside a fenced code block, with where it starts,
    and whether a fence was left open at the end.

    The one scanner: everything that looks for a heading, or for the link under
    `## Node`, asks this and never the raw text. An INDENTED code block needs
    no rule of its own — a heading carries at most three spaces and every line
    of an indented block carries four.
    """
    lines: list[tuple[int, str]] = []
    fence = ""
    at = 0
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\n")
        opened = FENCE.match(bare)
        if fence:
            if (opened and opened["mark"][0] == fence[0]
                    and len(opened["mark"]) >= len(fence) and CLOSES.match(opened["info"])):
                fence = ""
        elif opened:
            fence = opened["mark"]
        else:
            lines.append((at, bare))
        at += len(line)
    return lines, bool(fence)
