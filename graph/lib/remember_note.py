"""The bytes of one memory relative, and whether they are still the command's.

**A note is the command's, whole, or it is not the command's at all.** There is
no reading of a person's Markdown here, and nothing decides which parts of a
file to keep. Four rounds of review each found another spelling the scanner
read wrong — a heading after a tab, a heading hidden behind an inline pair of
backticks — and each time somebody's text was deleted. Parsing Markdown by hand
to decide what to delete was the defect; a better scanner was never the fix.

So the note carries a digest of its own body in its own front matter, and a
file is the command's to rewrite only when it is byte for byte what the command
last wrote. One edit of any kind, anywhere — a heading, a trailing space, a key
of somebody's own, one byte — and it is a person's: kept exactly as it is, and
the run says so.

A person who wants to write beside a card writes a relative of their own; this
one is a projection of the log and says nothing that is not in the log.
"""

from __future__ import annotations

import hashlib

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

MARK = " — from the log"
NODE = "Node"
KIND = "memory"
EDGE = "---\n"


def render(target: str, written: list) -> str:
    """This node's memory as it should stand. `target` is the link the vault
    resolves (`T26/02-schema`) and `written` is what the log says, as
    (heading, body) pairs in the order it happened."""
    body = _body(target, written)
    return _block(target, _digest(body)) + body


def ours(raw: bytes, target: str) -> bool:
    """Whether this file is byte for byte what the command last wrote.

    The only question asked of an existing file, and the only door to writing
    one. Anything it cannot answer yes to — text that is not UTF-8, no front
    matter, a digest that no longer matches the body, a `node` naming another
    card, an empty file — is a person's business and stays as it is.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    block, body = _split(text)
    return bool(block) and block == _block(target, _digest(body))


def _split(text: str) -> tuple[str, str]:
    """(the front-matter block, both `---` lines and all, the body), or two
    empty strings when this is not a note with front matter."""
    if not text.startswith(EDGE):
        return "", ""
    end = text.find("\n" + EDGE, len(EDGE) - 1)
    if end < 0:
        return "", ""
    return text[:end + len(EDGE) + 1], text[end + len(EDGE) + 1:]


def _block(target: str, digest: str) -> str:
    """The front matter this command writes, and the only one it recognises."""
    return EDGE + yaml.safe_dump(
        {"kind": KIND, "node": f"[[{target}]]", "digest": digest},
        sort_keys=False, allow_unicode=True).rstrip() + "\n" + EDGE


def _body(target: str, written: list) -> str:
    """The `## Node` list, then one dated section per thing that happened."""
    pieces = [f"## {NODE}\n\n- [[{target}]]"]
    pieces += [f"## {heading}{MARK}\n\n{said}" for heading, said in written]
    # The leading blank line is the body's own, so the digest covers it and a
    # note reads back exactly as it was written.
    return "\n" + "\n\n".join(pieces) + "\n"


def _digest(body: str) -> str:
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
