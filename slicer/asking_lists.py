"""What a prompt shows a model about the backlog: the roster line, the full
contracts, and what replaced what.

Split from `asking` at the 200-line cap. The listings are what the size
ceiling is about, so they and it live together; `asking` holds the prompts
that use them and stays the one door for the names.
"""

from __future__ import annotations

import yaml  # type: ignore[import-untyped]
from contracts import ATOM, BASE

# Loud, never cut: a listing too big to fit stops the run instead of handing a
# model one silently truncated mid-document.
#
# This ceiling is per LISTING, not per prompt — a decision of 2026-09-08, taken
# because the coverage review cannot have both: complete contracts for the
# molecules that are not done are about 187,000 characters on the live tree, and
# no arrangement of the listings puts one prompt under this number. So each
# listing is sized on its own and refuses on its own, and the coverage prompt's
# four listings together are larger than this. A whole-prompt ceiling would be a
# decision about what to leave out, and nobody has taken it.
PROMPT_BUDGET = 120_000

# What a card DECLARES, from the validator that decides it (`contracts`), plus
# the three the loop supplies. Everything else on a row — worktree, session,
# rounds, rejections — is how the work went, never what was promised.
#
# `sliced_from` is here because `replacements` reads it: whose replacement a
# piece says it is decides what the coverage reviewer is told, so it has to
# decide the digest as well, or a piece could walk away from its parent under a
# verdict that had seen it there. It is written once, when a piece is cut, so it
# costs no churn. With `id` and `status` beside it the whole replacement listing
# is now settled by digested fields, the id prefix included.
CONTRACT = ATOM | BASE | {"id", "status", "sliced_from"}



def index(rows: list[dict]) -> str:
    """One line per row: id, status, files touched, goal's whole first line.

    Stands in for a full YAML dump of the whole queue, which a real backlog
    outgrows in weeks and which used to be cut at 60,000 characters with no
    notice — the planner never saw most of what it was replanning around.
    Only this compact index counts against the budget: approved source text
    is sized by what was approved, not by how large the queue has grown.
    """
    lines = []
    for row in rows:
        goal_lines = (row.get("goal") or "").splitlines()
        first_line = goal_lines[0].strip() if goal_lines else ""
        joined_files = ", ".join(row.get("files") or [])
        lines.append(f"{row.get('id')} [{row.get('status')}] files={joined_files} — {first_line}")
    text = "\n".join(lines)
    if len(text) > PROMPT_BUDGET:
        over = len(text) - PROMPT_BUDGET
        raise ValueError(
            f"the queue is too large to plan against: {over} characters over "
            f"the budget of {PROMPT_BUDGET}")
    return text


def contract_text(rows: list[dict]) -> str:
    """Every card as it was declared — `gate` and `done_when` included.

    One line per row hid both, so a card rewritten to prove something else read
    as the same card. Run state is left out on purpose: a build that fills in a
    worktree or a round count has changed no promise."""
    kept = [{key: row[key] for key in sorted(row) if key in CONTRACT} for row in rows]
    return yaml.safe_dump(kept, sort_keys=True) if kept else "none"


def contracts_shown(rows: list[dict]) -> str:
    """`contract_text` for a prompt: loud past the budget, never cut."""
    text = contract_text(rows)
    if len(text) > PROMPT_BUDGET:
        raise ValueError(
            f"the contracts to review are too large: {len(text) - PROMPT_BUDGET} "
            f"characters over the budget of {PROMPT_BUDGET}")
    return text


def replacements(rows: list[dict]) -> str:
    """One line per replaced molecule: what replaced it, read from each piece's
    own `sliced_from`.

    A parent's `needs` cannot answer this. It holds prerequisites, and it does
    not have to hold the pieces: on the live tree `T12` is sliced, its `needs`
    names only the long-finished `T1`, and seven other rows declare
    `sliced_from: T12`.

    Two links, because the tree has two. `sliced_from` is what a piece records
    when it is cut; and an id is where a piece sits, so `T4.signin` is a piece
    of `T4` whether or not anything wrote the field down (`molecule.atom_id`
    builds exactly that name, and T4's own three pieces predate the field). A
    parent neither link reaches is said so out loud — that is a claim with
    nowhere left to live, and the reviewer must see it."""
    made: dict[str, list[str]] = {}
    for row in rows:
        name = str(row.get("id") or "")
        parents = {str(row.get("sliced_from") or ""), name.rsplit(".", 1)[0] if "." in name else ""}
        for parent in parents - {"", name}:
            made.setdefault(parent, []).append(name)
    lines = [f"{row.get('id')} replaced by: "
             + (", ".join(dict.fromkeys(made.get(str(row.get("id")), [])))
                or "nothing declares itself a replacement")
             for row in rows if row.get("status") == "sliced"]
    return "\n".join(lines) or "none"
