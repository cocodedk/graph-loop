"""File names in approved source text must have explicit card grants."""

import pathlib
import re

# ponytail: lexical file paths (including absent files), not natural-language
# descriptions; extend the recognizer when another source spelling is needed.
# Keep dotted names conservative: an ambiguous name cannot prove coverage.
NAME = re.compile(
    r"(?<![\w/.-])(?:\./)?(?:[\w.-]+/)+[\w.-]+"
    r"|(?<![\w/.-])[\w-]+(?:\.[\w-]+)*\.[A-Za-z][\w-]*"
    r"|(?<![\w/.-])(?:Dockerfile|Makefile|LICENSE)(?![\w/.-])")
URL = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s<>`]+")


def named_files(sources: list[pathlib.Path]) -> list[str]:
    names = set()
    for source in sources:
        text = URL.sub('', source.read_text('utf-8'))
        for match in NAME.finditer(text):
            names.add(str(pathlib.PurePosixPath(match.group().rstrip('.'))))
    return sorted(names)


def missing_files(names: list[str], rows: list[dict]) -> list[str]:
    granted = {str(pathlib.PurePosixPath(name))
               for row in rows for name in row.get('files') or []}
    return sorted(set(names) - granted)
