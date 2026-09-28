"""One feature of the lean loop (docs/rfc/lean-loop.md): build, check, publish.

A worktree off origin/main; one builder writes the feature and its tests; the
repository's own suite runs masked (`gates.run_gate`); one reviewer reads the diff.
A red suite or a refused review gets a repair pass with the failure text, up to
`REPAIRS` of them. A builder or reviewer that gave no real answer (a limit, a busy
provider, a lapsed sign-in, a crash) gets none. Still red, or unanswered: the person is
emailed why, and the feature stops with its worktree kept. Green, with the reviewer's
verdict: the change is committed, pushed as `lean/<feature>` and opened as a pull
request carrying the reviewer's findings, accepted or still refused; main never moves.
The spec file's front matter records how it ended.
"""

from __future__ import annotations

import os
import pathlib
import re

import accounts
import gate_paths
import gates
import lean_git
import lean_spec
import providers
import review
import tools
from lean_spec import record
from providers import REVIEW_EFFORT  # the one review effort, for both loops
from review_scope import VERDICT
from worktree import Worktree  # noqa: F401 — tests patch lean_run.Worktree

CLAUDE_BIN = os.environ.get("GRAPH_CLAUDE", "claude")
CODEX_BIN = os.environ.get("GRAPH_CODEX", "codex")
REPAIRS = 2   # repair passes after the first build; a repair often surfaces one more finding
REPAIR_EFFORT = "high"   # a repair round is handed why the last one fell short (2026-09-26 trial)


def build(ws, task: dict, prompt: str, tree, resume: str = "",
          effort: str = providers.EFFORT) -> providers.Outcome:
    """One builder call in the worktree, at `effort`, with the builder tool set for this suite."""
    feature, account = task["id"], accounts.available()[0]
    out = providers.claude(CLAUDE_BIN, prompt, account=account, cwd=tree.path, resume=resume,
                           effort=effort, allowed_tools=tools.builder_tools(task),
                           disallowed_tools=tools.builder_denies(task))
    ws.attempt(feature, account=account, kind=out.kind, cost=out.cost, tokens=out.tokens,
               effort=effort, purpose="build")
    return out


def masked(ws, command: str, cwd: str) -> tuple[bool, str]:
    """A profile command (suite or build), in the gate box: its verdict and its tail."""
    result = gates.run_gate(command, cwd, **gate_paths.options(ws.root))
    return result.passed, result.why


def judge(ws, feature: str, spec: str, diff: str, cwd: str) -> providers.Outcome:
    prompt = (f"You review one change to this repository, read-only. It should implement the "
              f"spec below, with tests. Refuse only for: something the spec's 'Done when' or "
              f"acceptance tests name that does not hold, a failure a user would meet in ordinary "
              f"use, a security hole, or behaviour added without tests. List anything rarer as a "
              f"finding, and accept. In this review an ACCEPT may carry findings, whatever the "
              f"answer rule below says.\n\n"
              f"## Spec\n\n{spec}\n\n## The diff against main\n\n{diff}\n\n{VERDICT}")

    def paid(kind, account, cost, tokens, _text):
        ws.attempt(feature, account=account, kind=kind, cost=cost, tokens=tokens,
                   effort=REVIEW_EFFORT, purpose="review")
    return review.codex(CODEX_BIN, prompt, cwd=cwd, effort=REVIEW_EFFORT, attempt=paid)


def grill(ws, repo: str, spec_paths: list[str], profile_path: str) -> str:
    """Before anything is built: the questions only a person can answer, or ""."""
    specs = "\n\n".join(f"## {pathlib.Path(path).name}\n\n{pathlib.Path(path).read_text('utf-8')}"
                        for path in spec_paths)
    prompt = (f"You read this spec before it is built, read-only; the repository's CLAUDE.md, "
              f"its brief and the profile at {profile_path} give the context. A builder implements "
              f"it next. It edits files and runs git, the suite and the programs the suite uses; it "
              f"cannot commit or push. The suite is "
              f"the profile's command, run on this machine with its network and Docker in a scrubbed "
              f"environment; your own read-only sandbox may be unable to run it, and that is no "
              f"question for the person. Refuse only for what a person "
              f"must decide first: a spec that contradicts itself, a decision the "
              f"builder would have to guess, or a requirement it cannot meet here. Each finding is one "
              f"question to the person. What the builder can settle itself is no question: accept."
              f"\n\n{specs}\n\n{VERDICT}")

    def paid(kind, account, cost, tokens, _text):
        ws.attempt("grill", account=account, kind=kind, cost=cost, tokens=tokens,
                   effort=REVIEW_EFFORT, purpose="grill")
    out = review.codex(CODEX_BIN, prompt, cwd=repo, effort=REVIEW_EFFORT, attempt=paid)
    questions = "" if out.verdict == "ACCEPT" else (out.text or f"the grill did not answer ({out.kind})")
    ws.event("lean_grilled", verdict=out.verdict, outcome=out.kind, questions=questions[:2000])
    if questions:
        subject = ("graph-loop has questions before building" if out.verdict
                   else "graph-loop could not read the specs before building")
        mail(ws, subject, f"{questions}\n\nAnswer them in the specs, then run again. Nothing was built.")
    return questions


def mail(ws, subject: str, body: str) -> None:
    """Through the proven contact; a failed send is logged, never raised."""
    ws.mail_person(subject, body)


def slug(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", pathlib.Path(path).stem).strip("-") or "feature"


def check(ws, feature: str, spec: str, tree, built, command: str, round_: int,
          revising: bool = False) -> tuple[str, providers.Outcome | None]:
    """Why this round is not done ("" when it is), and the reviewer's answer when it
    was asked. A revision answers review threads on its open pull request: the suite
    judges it here, and the reviewer who raised the threads reads it there."""
    if not built.ok:
        return f"the builder did not finish ({built.kind}): {built.text[:500]}", None
    diff = tree.diff(against=tree.commit)
    if not diff.strip():
        return "the builder changed nothing", None
    passed, tail = masked(ws, command, tree.path)
    ws.event("lean_suite", task=feature, round=round_, passed=passed, tail=tail[-2000:])
    if not passed:
        return f"the suite is red ({command}):\n{tail}", None
    if revising:
        return "", None
    verdict = judge(ws, feature, spec, diff, tree.path)
    ws.event("lean_review", task=feature, round=round_, outcome=verdict.kind,
             verdict=verdict.verdict, findings=verdict.text[:1000])
    if verdict.verdict != "ACCEPT":
        return f"the review did not accept ({verdict.kind}, {verdict.verdict}): {verdict.text}", verdict
    return "", verdict


def pr_body(spec_path: str, why: str, verdict) -> str:
    """What a new pull request says: the suite, the reviewer's verdict, its findings. A
    clean ACCEPT's text is its bare answer line (`review_read._read_review`), not a finding."""
    said = "accepted it" if not why else "still did not accept it after the last repair"
    found = "" if verdict.text.lstrip().startswith("{") else verdict.text.strip()
    return (f"Built by graph-loop's lean loop from `{pathlib.Path(spec_path).name}`: the suite "
            f"is green, and an independent reviewer {said}."
            + (f"\n\nThe reviewer's findings:\n\n{found}" if found else ""))


def run_feature(ws, repo: str, spec_path: str, profile: dict, profile_path: str,
                revise: str = "", pr: str = "") -> str:
    """One spec file, start to end. Its pull request's URL, or "" when it stopped.
    `revise` is the open pull request's review findings: fix them on its branch."""
    feature = slug(spec_path)
    spec = pathlib.Path(spec_path).read_text("utf-8")
    tree, last = lean_spec.start(repo, feature, spec, revise)
    ws.event("lean_feature_started", task=feature, spec=str(spec_path), base=tree.commit,
             tree=tree.path, resumed=bool(last))
    task = {"id": feature, "gate": profile["suite_command"]}
    script = tools.write_gate_script(task)   # the builder may run it: `bash <script>`
    prompt = (f"Implement what this spec asks, including its tests. Follow the repository's "
              f"CLAUDE.md and the profile at {profile_path}. Run the suite with "
              f"`bash {script}` and leave it green. Do not commit: the loop commits.\n\n"
              f"## Spec\n\n{spec}")
    built = build(ws, task, f"{prompt}\n\n## Your last attempt failed\n\n{last}\n\nThe work so far is "
                  "in this checkout: fix that, and keep the suite green." if last else prompt, tree,
                  effort=providers.EFFORT)
    why, verdict = check(ws, feature, spec, tree, built, profile["suite_command"], 1, bool(revise))
    for round_ in range(2, 2 + REPAIRS):
        # Only a real answer is worth a repair (`Outcome.consumes_attempt`): a builder or a
        # reviewer that hit a limit, was busy, signed out or broke stops the run, rounds kept.
        if not why or not built.ok or (verdict is not None and not verdict.ok):
            break
        ws.event("lean_repair", task=feature, why=why[-2000:])
        built = build(ws, task, f"{prompt}\n\n## Your last attempt failed\n\n{why}\n\n"
                      "Fix that, and keep the suite green.", tree, resume=built.session,
                      effort=REPAIR_EFFORT)
        why, verdict = check(ws, feature, spec, tree, built, profile["suite_command"], round_,
                             bool(revise))
    # A green suite whose reviewer gave a verdict is published, refused or not: after the
    # last repair, what the reviewer still finds goes to the pull request, not to a stop.
    if not why or (verdict is not None and verdict.verdict in ("ACCEPT", "REJECT")):
        try:
            title = f"feat({feature}): {feature}"
            work = lean_git.commit(repo, tree.path, tree.commit, title)
            url = lean_git.update(repo, work, feature, pr) if revise else lean_git.publish(
                repo, work, feature, title, pr_body(spec_path, why, verdict))
        except RuntimeError as error:
            why = f"it passed, but could not open its pull request: {error}"
        else:
            ws.event("lean_published", task=feature, commit=work, pr=url)
            record(spec_path, lean_status="pr_open", lean_pr=url)
            try:
                tree.remove()
            except OSError as error:   # files a suite's container left as root: tidy later
                ws.event("lean_tree_left", task=feature, tree=tree.path, error=str(error)[:300])
            return url
    kept = tree.keep(why)
    if not revise:                   # a revision that stopped leaves its pull request open
        record(spec_path, lean_status="stopped", lean_worktree=kept)
    ws.event("lean_stopped", task=feature, why=why[-2000:], tree=kept)
    mail(ws, f"graph-loop needs you: {feature}",
         f"{feature} stopped.\n\nWhy:\n{why}\n\nIts work is kept at {kept}.")
    return ""
