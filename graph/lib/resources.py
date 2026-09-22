"""One conveyor belt of resources, for every part of the loop that spends one.

The owner, 2026-08-31: "the same conveyor belt must provide resources to build,
review, supervisor, loop, whatever which needs resources."

A resource is an account and a model together — the two things a call needs and
the two things that run out. Each job asks for its candidates and walks them
until one answers. Nothing compiles a name in, so a resource that is expired,
exhausted or at capacity is replaced rather than fatal, which is the whole
reason there is more than one of each.

Every job's belt is the product of what the job can use:

    build    each builder model, on its agent and eligible accounts
    plan     each planner model, strong first, on every Claude account
    review   every reviewer model, then claude on every account — a review is
             read-only, so any agent that can read the repository can give one, so no account
    decide   the review belt: a decision reads the repository and answers with
             text, so whatever can review can decide (the caller spends the
             first rung at max — one decision is worth the ceiling)

Adding a resource is a line of data in `accounts.py` or `models.py`, or an
environment variable: GRAPH_ACCOUNTS, GRAPH_BUILDERS, GRAPH_REVIEWERS.
"""

from __future__ import annotations

import dataclasses

import accounts
import models


@dataclasses.dataclass(frozen=True)
class Resource:
    """One thing to try: the agent that runs it, the account it spends, the model.

    `agent` is the program: `claude` or `codex`. The belt supplies the
    program, account and model together for each job.
    """
    agent: str
    account: str | None
    model: str

    def __str__(self) -> str:
        return f"{self.agent}:{self.account}/{self.model}" if self.account else f"{self.agent}:{self.model}"


def belt(job: str) -> list[Resource]:
    """Every resource this job may spend, in the order to try them."""
    if job == "review":
        # codex first (every reviewer model in models.py's order — astra, then
        # sol since 2026-09-08), then claude on every account. A review reads
        # and writes nothing, so the last reviewer can be a different agent —
        # and one must be: when this account's codex offered a single model, a
        # capacity refusal left the loop with no reviewer and changes went in
        # unreviewed. The claude rungs have their OWN list: they read
        # `models.builders()` until 2026-09-18, so on a machine without codex
        # every change was reviewed by the model that wrote it.
        return ([Resource("codex", None, model) for model in models.reviewers()]
                + [Resource("claude", account, model)
                   for account in accounts.available()
                   for model in models.claude_reviewers()])
    if job == "decide":
        # The same resources, for the same reason: a decision reads and writes
        # nothing. It is its own job because what a planner is worth per call
        # is not what a reviewer is worth — the caller reads this name to know
        # it may spend the ceiling on the first rung — and because a decision
        # must not go unmade while one model is at capacity.
        return belt("review")
    if job in ("build", "plan"):
        candidates = models._PLANNERS if job == "plan" else models.builders()
        return [Resource(models.builder_agent(model), account, model)
                for model in candidates
                if job == "build" or models.builder_agent(model) == "claude"
                for account in ([None] if models.builder_agent(model) == "codex"
                                else accounts.available())]
    raise KeyError(f"no belt for {job!r}; the loop knows build, plan, review and decide")


class Exhausted:
    """What has run out so far, so the belt skips what cannot answer.

    The two refusals run out differently. A usage limit or an expired session
    belongs to the ACCOUNT: every model on it is refused, so the belt skips to
    the next account. A model at capacity belongs to the MODEL: the same account
    may answer on another one. Trying the wrong next thing spends a call to be
    told the same thing twice.
    """

    def __init__(self) -> None:
        self.accounts: set = set()
        self.models: set = set()

    def skip(self, resource: Resource) -> bool:
        return _identity(resource.account) in self.accounts or resource.model in self.models

    def note(self, resource: Resource, kind: str) -> None:
        if kind in ("limit", "auth"):
            self.accounts.add(_identity(resource.account))
        elif kind == "capacity":
            self.models.add(resource.model)


def _identity(account: str | None) -> str:
    """What actually runs out: the credential, not the label.

    Two configured names can point at one directory, and a limit on the first
    would leave the second looking fresh — the same session, asked again.
    """
    if account is None:
        return ""
    try:
        return str(accounts.home(account))
    except KeyError:
        return account


def refused_before_reading(kind: str) -> bool:
    """Whether this outcome means the resource itself was unavailable.

    These are the refusals another resource can answer: the model never read the
    question, so asking a different one asks the same question. A crash, a
    malformed answer or a harness fault is not on this list — those follow the
    work, not the resource, and another resource repeats them.
    """
    return kind in ("capacity", "limit", "auth")
