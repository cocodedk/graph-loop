"""Every model the loop may spend, in order, for each job it has.

The loop keeps more than one account so an exhausted one never stops the work.
The same must be true of models: on 2026-08-31 the reviewer answered "Selected
model is at capacity" three times, and because one model name was compiled into
the call, those reviews came back empty and the changes went in unreviewed.

One list per job, tried in order until one answers. GRAPH_BUILDERS,
GRAPH_REVIEWERS and GRAPH_CLAUDE_REVIEWERS override them without touching this
file — comma separated, and adding a model is a line of data.

Names, not families: what matters is that a second one exists, and that the
first refusal walks to it rather than stopping.
"""

from __future__ import annotations

import os

# The Claude builders first, Astra behind them (issue #67: the belt "may hold" codex
# rungs; the owner: "bigger models can plan and weaker models can execute").
_BUILDERS = ("claude-sonnet-5", "claude-opus-5-5", "claude-opus-5", "gpt-6-astra")
# Strong models shape the work; fast builders execute the resulting slices.
_PLANNERS = ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5")
# Checked against the binary, not guessed: gpt-6-astra answered `codex exec
# -m gpt-6-astra` on 2026-09-08 (the owner: the account's upgrade, high effort,
# strong at reasoning) and was the default reviewer, gpt-5.6-sol behind it,
# until the choice below. The second AGENT (claude) is still what
# resources.belt('review') adds after the codex reviewers.
# The owner, 2026-09-25: the reviewer is gpt-6-sol at high; it answered
# `codex exec -m gpt-6-sol -c model_reasoning_effort=high` the same day.
_REVIEWERS = ("gpt-6-sol",)
# What the claude rungs of the review belt use when no codex answers. Its own
# list, and the STRONG model first: these rungs used to reuse `builders()`, so
# the moment the builder list was reordered to put the fast model first (the owner,
# 2026-09-18) a machine without codex reviewed every change with the same model
# that wrote it — which is the one thing a review is for (CLAUDE.md § Code: an
# independent reviewer, never the builder). Found on the first real campaign
# run, where a reviewer had to be stood in by hand to get one at all.
# claude-opus-5-5 answered `claude --model claude-opus-5-5` on 2026-09-22 and leads
# the strong models; opus 5 stays behind it so a refusal still walks somewhere.
_CLAUDE_REVIEWERS = ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5")


def _listed(variable: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(variable, "").strip()
    named = tuple(piece.strip() for piece in raw.split(",") if piece.strip())
    return named or fallback


def builders() -> tuple[str, ...]:
    return _listed("GRAPH_BUILDERS", _BUILDERS)


def reviewers() -> tuple[str, ...]:
    return _listed("GRAPH_REVIEWERS", _REVIEWERS)


def claude_reviewers() -> tuple[str, ...]:
    """The claude rungs of the review belt: never the builder list."""
    return _listed("GRAPH_CLAUDE_REVIEWERS", _CLAUDE_REVIEWERS)


def builder_agent(model: str) -> str:
    """GPT names use Codex; existing Claude names and aliases stay on Claude."""
    return "codex" if model.startswith("gpt-") else "claude"
