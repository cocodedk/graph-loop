"""The question a contract reviewer is asked about each file the gate never names.

The gate IS the verdict, so a file the gate does not mention is a file whose
content the verdict does not pin. A card may hold write authority over one
anyway — a fixture read through a directory, a resource loaded by name at
runtime — and then whatever the builder puts in it is whatever the card
asserted against.

That is how one campaign built an extractor for a page format nobody had seen.
The card granted itself four files under `test/resources`, its gate passed the
DIRECTORY to the test rather than the files, and its own note said the fixtures
were "minimal pages in the shape of the post JSON embedded in x.com's own public
page". Nothing in the repository declared that shape, so the gate proved the code
matched an invention, went green, and was kept (2026-09-18).

Measured on the twelve cards that campaign planned: ten carried a file grant,
and exactly the two extraction cards granted a file their own gate never named.
The other eight named every file they granted. So this is a narrow signal rather
than a general one, and it costs nothing on a card that has none.

It is a QUESTION and not a refusal, because the shape is legitimate too: a gate
that runs `pytest tests/` names no fixture under it and is perfectly honest. What
the reviewer can tell apart, and no rule here can, is whether the shape that file
imitates is declared anywhere the loop can read.
"""

from __future__ import annotations


def unpinned(task: dict) -> list[str]:
    """The files this card grants that its own gate skipped, in order.

    Skipped, not merely absent: a gate that names NONE of the card's files works
    at directory level — `pytest tests/` names no fixture under it and invents
    nothing — so it says nothing about any of them and this is empty. It is when
    a gate names some of its card's files and not others that the others stand
    out, because the card itself drew that line.
    """
    gate = str(task.get("gate") or "")
    files = [str(path) for path in (task.get("files") or [])]
    named = [path for path in files if path in gate]
    return [path for path in files if path not in gate] if named else []


def question(task: dict) -> str:
    """One paragraph, or nothing when the gate names every file the card grants."""
    files = unpinned(task)
    if not files or not str(task.get("gate") or "").strip():
        return ""
    return (
        "\nThis card's gate names some of the files it grants and not these, so the gate "
        "does not pin what goes in them. Take them one at a time, and for each one answer in your "
        "own head: if this file holds data the code under test reads, where is that "
        "data's shape declared — an approved source, or a file already in the "
        "repository? If the shape comes from OUTSIDE this repository and nothing here "
        "declares it, the builder will invent it, the gate will prove the code matches "
        "the invention, and it will go green — refuse the card and say what must be "
        "fetched or declared first. If the file is code the gate compiles or runs "
        "through a directory, or its shape is this repository's own, that is fine.\n"
        + "".join(f"  - {path}\n" for path in files))
