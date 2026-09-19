"""One card as one Obsidian note: front matter, headings, and wikilinks.

The note IS the card. There is no second representation and nothing is
generated from anything, so what a person reads in Obsidian is byte for byte
what the loop reads.

    ---
    status: todo
    files:
      - drive/lib/backlog.py
    ---

    ## Goal

    the signup form rejects a blank email

    ## Gate

    ```sh
    python3 -m unittest tests.test_signup
    ```

    ## Needs

    - [[T4/molecule]]

Front matter holds what the loop decides — `status`, `files`, the flags. The
body holds what a person wrote, and `Needs`, `Uses` and `Creates` are
`[[wikilinks]]`, so Obsidian's graph view is the dependency graph itself rather
than a picture of one.

A link is written as the note's path inside the vault (`T26/02-schema`) because
that is what Obsidian resolves; it is read back as the id the rest of the loop
uses (`T26.schema`). A link that names no note of the vault — a `path:text`
name, a card in another backlog — round-trips verbatim.
"""

from __future__ import annotations

import pathlib
import re

import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from front_matter import entry as _entry

SUFFIX = ".md"
HEAD = f"molecule{SUFFIX}"
NUMBERED = re.compile(r"^(?P<order>\d+)-(?P<stem>.+)$")
FRONT = re.compile(r"\A---\r?\n(?P<front>.*?)(?:\r?\n)?^---[ \t]*\r?\n?(?P<body>.*)\Z",
                   re.DOTALL | re.MULTILINE)
SECTION = re.compile(r"(?m)^## +(?P<heading>.+?)[ \t]*$")
FENCED_BLOCK = re.compile(r"\A`{3,}[^\n]*\n(?P<inside>.*?)\n?`{3,}\s*\Z", re.DOTALL)
LINK = re.compile(r"(?m)^[-*] +\[\[(?P<target>[^\]]+)\]\]\s*$")

# The body of a note, in the order it is written. Every other key is front
# matter, so a field the loop adds later needs no change here.
BODY = ("goal", "why", "done_when", "gate", "needs", "uses", "creates", "note")
LINKED = ("needs", "uses", "creates")
FENCED = ("gate",)


def load(path: pathlib.Path) -> dict:
    """One note, read. A card that will not parse says WHICH card.

    `backlog_tree.read` loads every note in the vault, so one bad one stops
    `status`, `plan`, `run`, `doctor` and `report` alike — and the raw traceback
    named none of them, which meant finding it by hand (2026-09-18). This is
    the only place that knows the path.
    """
    try:
        return parse(path.read_text("utf-8"))
    except (ValueError, yaml.YAMLError) as unreadable:
        raise ValueError(f"{path} is not a readable card: {unreadable}") from unreadable


def parse(text: str) -> dict:
    """The note as the mapping the rest of the loop reads."""
    found = FRONT.match(text)
    if not found:
        raise ValueError("a card is a note: front matter between --- lines, then its body")
    card = yaml.safe_load(found["front"]) or {}
    if not isinstance(card, dict):
        raise ValueError("a card's front matter is a mapping")  # noqa: TRY004 — one channel
    for heading, section in _sections(found["body"]):
        card[heading.strip().lower().replace(" ", "_")] = _value(heading, section)
    return card


def dump(card: dict, link=None) -> str:
    """The note that reads back as this card. `link` turns an id into the note
    that holds it; without one, every link is written as it stands."""
    front = {key: value for key, value in card.items() if key not in BODY}
    out = ["---", yaml.safe_dump(front, sort_keys=False, width=100,
                                 allow_unicode=True).rstrip(), "---"]
    for field in BODY:
        value = card.get(field)
        if value is None or value == "" or value == []:
            continue
        out += ["", f"## {field.replace('_', ' ').capitalize()}", "",
                _written(field, value, link)]
    return "\n".join(out) + "\n"


def patch(text: str, field: str, value) -> str:
    """One front-matter field written, every other byte of the note left alone.

    The loop writes `status` at each transition and a triage verdict at a
    boundary; both come through here, so nothing the loop does reaches the
    prose, the headings, the comments or the line endings a person wrote.
    `None` takes the field out. A field the note does not carry is added at the
    end of its front matter.
    """
    found = FRONT.match(text)
    if not found:
        raise ValueError("a card is a note: front matter between --- lines, then its body")
    front = found["front"]
    ending = "\r\n" if "\r\n" in front else "\n"
    written = "" if value is None else ending.join(
        yaml.safe_dump({field: value}, sort_keys=False, width=100,
                       allow_unicode=True).rstrip("\n").split("\n"))
    where = _entry(front, field)
    if where is None:
        block = written if not front else front + (ending + written if written else "")
    else:
        start, stop = where
        after = front[stop:]
        if not written:                       # taken out, and its line ending with it
            after = after[len(ending):] if after.startswith(ending) else after.lstrip("\r\n")
        block = front[:start] + written + after
    begins, ends = found.span("front")
    return text[:begins] + block + text[ends:]


def linker(root: pathlib.Path):
    """id → the note holding it, so `[[T26/02-schema]]` opens in Obsidian.

    Read from the vault, never from a list kept beside it: a hand-written map of
    what is where drifts from the tree it describes.
    """
    where: dict[str, str] = {}
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.name.startswith(".") or not (folder / HEAD).exists():
            continue
        where[folder.name] = f"{folder.name}/molecule"
        for path in sorted(folder.iterdir()):
            found = NUMBERED.match(path.stem)
            if path.suffix == SUFFIX and found:
                where[f"{folder.name}.{found['stem']}"] = f"{folder.name}/{path.stem}"
    return lambda name: where.get(name, name)


def unlink(target: str) -> str:
    """A wikilink's target as the id the loop uses. A target that is not a note
    of this vault is its own id — `path:text` names come back untouched."""
    folder, slash, leaf = target.strip().rpartition("/")
    if not slash or "/" in folder:
        return target.strip()
    if leaf == "molecule":
        return folder
    found = NUMBERED.match(leaf)
    return f"{folder}.{found['stem']}" if found else target.strip()


def _sections(body: str):
    pieces = SECTION.split(body)
    return list(zip(pieces[1::2], pieces[2::2], strict=True))


def _value(heading: str, section: str):
    field = heading.strip().lower().replace(" ", "_")
    if field in LINKED:
        return [unlink(found["target"]) for found in LINK.finditer(section)]
    if field in FENCED:
        inside = FENCED_BLOCK.match(section.strip())
        return inside["inside"] if inside else section.strip()
    return section.strip()


def _written(field: str, value, link) -> str:
    if field in LINKED:
        say = link or (lambda name: name)
        return "\n".join(f"- [[{say(str(name))}]]" for name in value)
    if field in FENCED:
        # Not stripped: a gate's own trailing newline is part of the text the
        # loop hashes and runs, and dropping it changed every gate once.
        body = str(value)
        fence = "`" * max(3, *(len(run) + 1 for run in re.findall(r"`+", body)), 3)
        return f"{fence}sh\n{body}\n{fence}"
    return str(value).strip()
