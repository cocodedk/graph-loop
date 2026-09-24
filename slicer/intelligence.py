"""Read-only model calls for the speccer and slicer, from the graph resource belt."""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import subprocess
import sys

GRAPH_LIB = pathlib.Path(__file__).resolve().parents[1] / "graph" / "lib"
sys.path.insert(0, str(GRAPH_LIB))

import accounts  # type: ignore[import-not-found]
import providers  # type: ignore[import-not-found]
import resources  # type: ignore[import-not-found]
import runner as process_runner  # type: ignore[import-not-found]  # `runner` is this module's own keyword
import tools  # type: ignore[import-not-found]


@dataclasses.dataclass(frozen=True)
class Reply:
    ok: bool
    text: str = ""
    why: str = ""
    down: bool = False        # the call itself failed; nobody judged anything


def _argv(resource) -> list[str]:
    return [
        os.environ.get("GRAPH_CLAUDE", "claude"), "-p", "--output-format", "json",
        "--permission-mode", "dontAsk", "--no-session-persistence",
        *tools.READ_ONLY_FLAGS,
        "--allowedTools", tools.READ, "--disallowedTools",
        f"Agent,MultiEdit,{tools.READ_ONLY_DENIES}",
        "--model", resource.model, "--effort", "medium",
    ]


CAMPAIGN: pathlib.Path | None = None


def _attempt(kind: str, account, cost=None, tokens=None) -> None:
    """Every model call the slicer makes lands in the campaign's own ledger,
    or spend and futility vanish from the record."""
    if CAMPAIGN is None:
        return
    try:
        from workspace import Workspace  # type: ignore[import-not-found]
        Workspace(CAMPAIGN).attempt("the slicer", account=str(account or "plan"),
                                    kind=kind, cost=cost, tokens=tokens,
                                    # spend is still counted; the build's
                                    # futility window is not (`watchdog.PLANNING`)
                                    purpose="plan")
    except OSError:
        pass


def _call(step: str, prompt: str, answer: str, seconds: float, **fields) -> None:
    """Each resource's timed call, with its prompt and answer, in the
    campaign's own step and artifact records (SLICER.md: every call uses
    the existing attempt, step and artifact records)."""
    if CAMPAIGN is None:
        return
    try:
        from workspace import Workspace  # type: ignore[import-not-found]
        space = Workspace(CAMPAIGN)
        space.event("step", task="the slicer", step=step,
                    seconds=round(seconds, 3), **fields)
        space.artifact("the slicer", f"{step}-prompt", prompt)
        space.artifact("the slicer", f"{step}-answer", answer)
    except OSError:
        pass


def ask(prompt: str, repo: pathlib.Path, *, runner=process_runner.run) -> Reply:
    """Ask the plan belt with only Read, Grep and Glob available.

    Through the graph loop's one runner, like every other paid child: the
    planner leads its own process group, so it ends when this call ends, and
    it dies with this slicer — which dies with the driver. Started by
    `subprocess.run`, a planner outlived the driver that was paying for it.
    """
    spent = resources.Exhausted()
    last = Reply(False, why="the plan belt is empty")
    for resource in resources.belt("plan"):
        if spent.skip(resource):
            continue
        environment = dict(os.environ)
        added, dropped = accounts.environment(str(resource.account or ""))
        environment.update(added)
        for name in dropped:
            environment.pop(name, None)
        import time
        started = time.time()
        try:
            done = runner(_argv(resource), stdin=prompt, env=environment, cwd=str(repo),
                          timeout=providers.PLAN_TIMEOUT)
        except subprocess.TimeoutExpired:
            _attempt("crash", resource.account)
            _call("plan", prompt, "(no answer inside the timeout)",
                  time.time() - started, account=str(resource.account or ""))
            return Reply(False, why="the planner did not return inside its timeout")
        blob = (done.stdout or "") + (done.stderr or "")
        _call("plan", prompt, blob, time.time() - started,
              account=str(resource.account or ""), rc=done.returncode)
        try:
            body = json.loads(done.stdout)
        except (TypeError, ValueError):
            body = {}
        answer = str(body.get("result") or "").strip() if isinstance(body, dict) else ""
        # one reader for what a call spent, success or not: a refusal carries
        # its own numbers, an explicit zero stays zero, junk stays unknown
        spend = providers._spent(body if isinstance(body, dict) else {})
        if answer and not body.get("is_error"):
            _attempt("ok", resource.account,
                     cost=spend.get("cost"), tokens=spend.get("tokens"))
            return Reply(True, answer)
        kind = providers._classify_text(blob)
        _attempt(kind or "malformed", resource.account,
                 cost=spend.get("cost"), tokens=spend.get("tokens"))
        last = Reply(False, why=(answer or blob.strip() or "planner returned no answer")[:500])
        if not kind or not resources.refused_before_reading(kind):
            return last
        spent.note(resource, kind)
    return last


def review(prompt: str, repo: pathlib.Path | None, *, binary: str | None = None) -> Reply:
    """One independent medium-effort verdict from the existing review belt.

    `repo` is the checkout the review reads — the same clean one the planner
    was given. It has no default: a caller that leaves it out judged whatever
    directory the process happened to sit in, which for the driver is its own
    working tree and not the campaign tip the slice was planned against.
    """
    import time
    last = [time.time()]

    def noted(kind, account, cost, tokens, text=""):
        now = time.time()
        _attempt(kind, account, cost=cost, tokens=tokens)
        _call("review", prompt, text or kind, now - last[0],
              outcome=kind, account=str(account or ""))
        last[0] = now

    out = providers.codex(binary or os.environ.get("GRAPH_CODEX", "codex"),
                          prompt, cwd=str(repo) if repo else "", effort="medium",
                          attempt=noted)
    if not out.ok:
        # `down` means NOBODY judged anything, and only a resource that refused
        # before reading the question is that. A reviewer that answered in a
        # shape the parser rightly refuses — a REJECT carrying accept: true —
        # has read the repository and said what is wrong, and filing that as
        # silence threw away three correct findings and put the card out of
        # reach of a repair round (2026-09-18). The graph side already draws
        # this line; this is the same one.
        silent = resources.refused_before_reading(out.kind)
        return Reply(False, text=out.text,
                     why=(f"the review did not happen ({out.kind}: {out.text})" if silent
                          else f"the reviewer answered but not in the closed shape "
                               f"({out.kind}): {out.text}"),
                     down=silent)
    return Reply(out.verdict == "ACCEPT", out.text,
                 "" if out.verdict == "ACCEPT" else out.text)
