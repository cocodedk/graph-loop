"""Calling a model, and reading the answer honestly.

Two providers: builders on `claude-opus-5-5` or a configured alias, reviewers on
`codex exec --model gpt-6-astra` or a configured alias. Which model and effort
an actual call uses is `model_router.choose`'s pick now (docs/ROUTER.md): a
Jev decision at medium, raised only from a recorded failed medium attempt on
the same contract. `MODEL`/`EFFORT`/`REVIEW_MODEL`/`REVIEW_EFFORT` below are
what a caller with no route of its own gets — medium, never `max`, which cost
twelve minutes a review and found what high finds (the owner, 2026-08-30).

The `kind` an outcome carries decides what the loop may conclude. Only `ok`
consumes an attempt: a usage limit, a denied tool call, a login failure and
output that is not the promised shape all say "no attempt happened", because
counting them as failures is how a ladder burns itself on the harness.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import tempfile

import accounts
from provider_call import _run  # the door stays here; provider_codex reads this module
from provider_words import (  # noqa: F401 — MARKS re-exported for callers that import them from here
    AUTH_MARKS,
    CAPACITY_MARKS,
    LIMIT_MARKS,
    _classify_failure,
    _classify_text,
    closed_object,
)
from tools import READ_ONLY_FLAGS, guard_settings

MODEL = "claude-opus-5-5"
EFFORT = "medium"               # the default when no task decides (model_router.py does)
REVIEW_MODEL = "gpt-6-astra"
REVIEW_EFFORT = "medium"        # the default when no task decides (model_router.py does)


@dataclasses.dataclass
class Outcome:
    kind: str            # ok | limit | capacity | harness | auth | malformed | crash
    text: str = ""
    cost: float | None = None
    tokens: int | None = None
    verdict: str | None = None
    denials: int = 0
    session: str = ""    # the call's own session id, so a rebuild round can resume it
    raw: str = ""
    confidence: float | None = None   # a decisions answer's own probability, not a boolean

    @property
    def ok(self) -> bool:
        return self.kind == "ok"

    @property
    def unstarted(self) -> bool:
        """A refusal that cost nothing: the call never reached the model.

        `kind` is decided by matching the answer's text, and text alone does not
        prove no tool ran — an answer could mention a refused session, or a limit,
        after a builder had already acted. Only a call that spent nothing did
        nothing, and that is the one a live task may safely try on another account.

        Both refusals a second account can answer are here: an expired session,
        and a usage limit reached before the first turn. A limit hit part way
        through a call carries its cost and is not unstarted.

        The zeroes must be there. A missing number is unknown, not nothing:
        reading `not (cost or 0)` made every refusal look free, because the
        error path dropped the numbers the answer actually carries.
        """
        return self.kind in ("auth", "limit", "capacity") and self.cost == 0 \
            and self.tokens == 0 \
            and not self.denials

    @property
    def consumes_attempt(self) -> bool:
        """Only a real answer counts. Everything else is the harness talking."""
        return self.kind == "ok"


def _spent(body: dict) -> dict:
    """What the call spent, read from the answer's own numbers.

    A refusal carries them too — an expired session answers with
    total_cost_usd 0 and a usage block of zeros — and the error path used to
    drop them, so every refusal looked like it had spent nothing whether it had
    or not. A field that is absent stays None: unknown is not zero.
    """
    usage = body.get("usage")
    tokens = None
    if isinstance(usage, dict):
        # BOTH counts, or none. A block that reports zero input and omits output
        # says nothing about what it spent, and summing what is there reads that
        # silence as zero — which is the proof a live retry rests on.
        counts = [value for value in (usage.get("input_tokens"), usage.get("output_tokens"))
                  if isinstance(value, int) and not isinstance(value, bool)]
        tokens = sum(counts) if len(counts) == 2 else None
    denials = body.get("permission_denials")
    cost = body.get("total_cost_usd")
    # A JSON boolean is an int in Python: `false` would read as zero spend, and
    # zero spend is the proof a live action may be repeated.
    money = cost if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None
    return {"cost": money, "tokens": tokens,
            # A missing list is unknown, not "no denials": -1 says so, and
            # `unstarted` refuses anything that is not exactly zero.
            "denials": len(denials) if isinstance(denials, list) else -1}


BUILD_TIMEOUT = 7200   # a builder's call: two hours — an hour cut a decision-table build off at 58 minutes
PLAN_TIMEOUT = 900     # a planner answers with text: fifteen minutes, or a stalled rewrite holds the whole loop


def claude(binary: str, prompt: str, *, account: str, allowed_tools: str = "",
           disallowed_tools: str = "", guard: str = "", guard_files: str = "",
           no_tools: bool = False, read_only: bool = False, effort: str = "", resume: str = "",
           timeout: int = BUILD_TIMEOUT, cwd: str | None = None,
           model: str = "") -> Outcome:
    """One builder call, in the task's own directory.

    Which configuration an account uses is `lib/accounts.py`'s to say, not this
    function's: a branch on one account's name here is why a third could not be
    added without editing code.
    """
    env, drop = accounts.environment(account)
    argv = [binary, "--permission-mode", "dontAsk", "--strict-mcp-config",
            "-p", "--output-format", "json",
            "--model", model or MODEL, "--effort", effort or EFFORT,
            "--disallowedTools", ",".join(name for name in ("Agent", disallowed_tools) if name)]
    if resume:
        # A rebuild round continues the SAME work: the builder keeps what it read
        # and gets the findings on top, instead of paying to read it all again.
        argv += ["--resume", resume]
    if allowed_tools:
        argv += ["--allowedTools", allowed_tools]
    if read_only:   # a reviewer reads and nothing else; the denies alone cannot
        argv += list(READ_ONLY_FLAGS)   # reach an inherited MCP server (tools.py)
    if no_tools:   # a planner answers with text: it edits nothing and touches no stack
        argv += ["--tools", ""]   # --strict-mcp-config above already keeps out an inherited MCP server
        # the families a planner must never have are denied by name as well.
        argv[argv.index("--disallowedTools") + 1] += ",Bash,Edit,Write,MultiEdit,NotebookEdit,Monitor,Workflow,WebFetch,Task"
    settings = None
    if guard:   # a live task: the guard hook first, its prefixes in the environment
        with tempfile.NamedTemporaryFile("w", suffix=".json", prefix="live-guard-", delete=False) as settings:
            json.dump(guard_settings(), settings)
        argv += ["--settings", settings.name]
        env = {**env, "LIVE_ALLOWED_PREFIXES": guard, "LIVE_ALLOWED_FILES": guard_files,
               "LIVE_WORKTREE": cwd or ""}
    try:
        done = _run(argv, prompt, env, timeout, cwd=cwd, drop=drop)
    except subprocess.TimeoutExpired:
        return Outcome("crash", text="the call did not return inside its timeout")
    finally:
        if settings:
            os.unlink(settings.name)
    blob = (done.stdout or "") + (done.stderr or "")
    try:
        body = json.loads(done.stdout)
    except (ValueError, TypeError):
        # No usable answer: now the words explain why, and a limit or a login
        # failure means no attempt happened.
        return Outcome(_classify_text(blob) or "malformed",
                       text=(done.stdout or done.stderr).strip()[:500], raw=blob)
    if not isinstance(body, dict):
        # Valid JSON of the wrong shape: an answer we cannot read is still an
        # answer, and raising here left a live task todo for the next turn.
        return Outcome("malformed", text=str(body)[:500], raw=blob)
    if failure := _classify_failure(body, done.returncode, blob):
        return Outcome(failure,
                       text=str(body.get("result") or "")[:500], raw=blob,
                       session=str(body.get("session_id") or ""), **_spent(body))
    if not isinstance(body.get("usage", {}), dict) or not isinstance(body.get("permission_denials", []), list):
        return Outcome("malformed", text="the answer's own fields are not the shape they claim", raw=blob)
    denials = body.get("permission_denials") or []
    answered = str(body.get("result") or "").strip()
    if denials and not answered:
        # Denied before it could do anything: a harness fault, no attempt made.
        return Outcome("harness", text=json.dumps(denials)[:500], raw=blob)
    # Denials that the caller worked around are worth reading, never a reason to
    # throw away finished work: a builder was refused three `cd &&` commands,
    # did the job anyway, and had five minutes of correct work discarded.
    return Outcome("ok", text=answered, session=str(body.get("session_id") or ""),
                   raw=blob, **{**_spent(body), "denials": len(denials)})


from provider_codex import codex_text  # noqa: F401 — the transport's own door
from review import codex  # noqa: F401 — the door stays here; review reads this module
