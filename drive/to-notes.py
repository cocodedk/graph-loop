#!/usr/bin/env python3
"""Turn a tree backlog written as YAML into the same tree written as notes, once.

    python3 drive/to-notes.py <backlog folder>

Every `.yaml` card becomes the `.md` note beside it and the `.yaml` goes, so a
campaign already under way carries on in the vault rather than starting again.
Field for field the same card: only the file it is written in changes.

Run it with the loop stopped. It writes each molecule whole or not at all.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
import cardfile  # type: ignore[import-not-found]
import yaml  # type: ignore[import-untyped]  # no stubs in this environment


def convert(root: pathlib.Path) -> int:
    moved = 0
    for folder in _molecules(root):
        cards = sorted(path for path in folder.iterdir() if path.suffix == ".yaml")
        # Written before anything is removed: a molecule half in each format is
        # read as half a molecule, and a crash here would leave one behind.
        for path in cards:
            body = yaml.safe_load(path.read_text("utf-8")) or {}
            path.with_suffix(cardfile.SUFFIX).write_text(cardfile.dump(body), "utf-8")
        for path in cards:
            path.unlink()
        moved += len(cards)
    relink(root)
    return moved


def relink(root: pathlib.Path) -> None:
    """Point every wait at the note that holds it, now that they all exist.

    A second pass rather than a cleverer first one: a link can only be written
    as a note's path once that note is on disk, and half the vault is not there
    while the first card is being converted.
    """
    link = cardfile.linker(root)
    for folder in _molecules(root):
        for path in sorted(folder.iterdir()):
            if path.suffix == cardfile.SUFFIX:
                path.write_text(cardfile.dump(cardfile.load(path), link), "utf-8")


def _molecules(root: pathlib.Path):
    return [folder for folder in sorted(root.iterdir())
            if folder.is_dir() and not folder.name.startswith(".")]


if __name__ == "__main__":
    where = pathlib.Path(sys.argv[1])
    if not where.is_dir():
        sys.exit(f"{where} is not a tree backlog")
    print(f"{convert(where)} cards are notes now in {where}")
