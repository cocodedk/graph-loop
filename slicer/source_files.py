"""Only structured Files/Creates fields declare work needing card grants."""

import pathlib
import re

FIELD = re.compile(
    r'^\s*(?:[-*+]\s+)?(?:\*\*)?(?:Files|Creates)(?:\*\*)?\s*:'
    r'(?:\*\*)?\s*(.*?)\s*$', re.IGNORECASE)
FENCE = re.compile(r'^\s*(`{3,}|~{3,})')
ITEM = re.compile(r'^\s+[-*+]\s+(.+)$')
LINK = re.compile(r'!?\[[^\[\]]*\]\([^)]*\)')
NAME = re.compile(
    r'(?:\./)?(?:[\w.-]+/)+[\w.-]+|[\w-]+(?:\.[\w-]+)+'
    r'|Dockerfile|Makefile|LICENSE')


def _names(value: str) -> set[str]:
    """A field contains a list of paths, not a sentence containing paths.

    Accept bare, quoted, backticked and wikilink entries, comma/space separated,
    including YAML inline lists. Markdown links and URLs are references.
    Creates may qualify a file with an exported symbol after a colon.
    """
    value = LINK.sub('', value).strip().strip('[]')
    names = set()
    for item in re.split(r'[,\s]+', value):
        item = item.strip('`\'"[]')
        if not item:
            continue
        name = item.split(':', 1)[0]
        if '://' in item or not NAME.fullmatch(name):
            return set()
        names.add(str(pathlib.PurePosixPath(name)))
    return names


def named_files(sources: list[pathlib.Path]) -> list[str]:
    """Read Markdown field lines and their indented list continuations.

    Prose, fenced examples, HTML comments and sources without these fields
    contribute nothing. No filesystem-existence check: new files are work too.
    """
    names = set()
    for source in sources:
        text = re.sub(r'<!--.*?(?:-->|\Z)', '', source.read_text('utf-8'), flags=re.DOTALL)
        fence = None
        listing = False
        for line in text.splitlines():
            marker = FENCE.match(line)
            if fence:
                if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) \
                        and not line[marker.end():].strip():
                    fence = None
                continue
            if marker:
                fence = marker[1]
                listing = False
                continue
            field = FIELD.fullmatch(line)
            if field:
                names.update(_names(field[1]))
                listing = not field[1]
            elif listing and (item := ITEM.fullmatch(line)):
                names.update(_names(item[1]))
            elif line.strip():
                listing = False
    return sorted(names)


def missing_files(names: list[str], rows: list[dict]) -> list[str]:
    granted = {str(pathlib.PurePosixPath(name))
               for row in rows for name in row.get('files') or []}
    return sorted(set(names) - granted)
