"""One feature of the lean loop (docs/rfc/lean-loop.md): build, check, land.

A worktree off the campaign branch (`lean_git.BRANCH`); one builder writes the feature and its tests; the
repository's own suite runs masked (`gates.run_gate`); one reviewer reads the
diff. A red suite or a refused review gets a repair pass with the failure
text, up to `REPAIRS` of them. Still failing: the person is emailed why, and the feature stops with its
worktree kept. Passing: the change is committed and landed on the branch, never on main.
"""

from __future__ import annotations

import os
import pathlib
import re

import accounts
import gate_paths
import gates
import lean_git
import providers
import review
import tools
from review_scope import VERDICT
from worktree import Worktree

CLAUDE_BIN = os.environ.get("GRAPH_CLAUDE", "claude")
CODEX_BIN = os.environ.get("GRAPH_CODEX", "codex")
REPAIRS = 2   # repair passes after the first build; a repair often surfaces one more finding


def build(ws, task: dict, prompt: str, tree, resume: str = "") -> providers.Outcome:
    """One builder call in the worktree, with the builder tool set for this suite."""
    feature, account = task["id"], accounts.available()[0]
    out = providers.claude(CLAUDE_BIN, prompt, account=account, cwd=tree.path, resume=resume,
                           allowed_tools=tools.builder_tools(task),
                           disallowed_tools=tools.builder_denies(task))
    ws.attempt(feature, account=account, kind=out.kind, cost=out.cost, tokens=out.tokens,
               purpose="build")
    return out


def masked(ws, command: str, cwd: str) -> tuple[bool, str]:
    """A profile command (suite or build), in the gate box: its verdict and its tail."""
    result = gates.run_gate(command, cwd, **gate_paths.options(ws.root))
    return result.passed, result.why


def judge(ws, feature: str, spec: str, diff: str, cwd: str) -> providers.Outcome:
    prompt = (f"You review one change to this repository, read-only. It should implement the "
              f"spec below, with tests. Refuse only for: something the spec's 'Done when' names "
              f"that does not hold, a failure a user would meet in ordinary use, a security hole, "
              f"or behaviour added without tests. List anything rarer as a finding, and accept.\n\n"
              f"## Spec\n\n{spec}\n\n## The diff against the branch it builds on\n\n{diff}\n\n{VERDICT}")

    def paid(kind, account, cost, tokens, _text):
        ws.attempt(feature, account=account, kind=kind, cost=cost, tokens=tokens, purpose="review")
    return review.codex(CODEX_BIN, prompt, cwd=cwd, attempt=paid)


def grill(ws, repo: str, spec_paths: list[str], profile_path: str) -> str:
    """Before anything is built: the questions only a person can answer, or ""."""
    specs = "\n\n".join(f"## {pathlib.Path(path).name}\n\n{pathlib.Path(path).read_text('utf-8')}"
                        for path in spec_paths)
    prompt = (f"You read these specs before anything is built, read-only; the repository's CLAUDE.md, "
              f"its brief and the profile at {profile_path} give the context. A builder implements "
              f"each spec in order. It edits files only (no chmod, no git, no network), and the suite "
              f"runs in a sandbox with an empty home and no network. Refuse only for what a person "
              f"must decide first: specs that contradict each other or themselves, a decision the "
              f"builder would have to guess, or a requirement it cannot meet here. Each finding is one "
              f"question to the person. What the builder can settle itself is no question: accept."
              f"\n\n{specs}\n\n{VERDICT}")

    def paid(kind, account, cost, tokens, _text):
        ws.attempt("grill", account=account, kind=kind, cost=cost, tokens=tokens, purpose="grill")
    out = review.codex(CODEX_BIN, prompt, cwd=repo, attempt=paid)
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


def check(ws, feature: str, spec: str, tree, built, command: str, round_: int) -> str:
    """Why this round is not done, or "" when it is."""
    if not built.ok:
        return f"the builder did not finish ({built.kind}): {built.text[:500]}"
    diff = tree.diff(against=tree.commit)
    if not diff.strip():
        return "the builder changed nothing"
    passed, tail = masked(ws, command, tree.path)
    ws.event("lean_suite", task=feature, round=round_, passed=passed, tail=tail[-2000:])
    if not passed:
        return f"the suite is red ({command}):\n{tail}"
    verdict = judge(ws, feature, spec, diff, tree.path)
    ws.event("lean_review", task=feature, round=round_, outcome=verdict.kind,
             verdict=verdict.verdict, findings=verdict.text[:1000])
    if verdict.verdict != "ACCEPT":
        return f"the review did not accept ({verdict.kind}, {verdict.verdict}): {verdict.text}"
    return ""


def run_feature(ws, repo: str, spec_path: str, profile: dict, profile_path: str) -> str:
    """One spec file, start to end. The new branch commit, or "" when it stopped."""
    feature = slug(spec_path)
    spec = pathlib.Path(spec_path).read_text("utf-8")
    tree = Worktree(repo, feature, commit=lean_git.BRANCH).create()
    ws.event("lean_feature_started", task=feature, spec=str(spec_path), base=tree.commit,
             tree=tree.path)
    task = {"id": feature, "gate": profile["suite_command"]}
    script = tools.write_gate_script(task)   # the builder may run it: `bash <script>`
    prompt = (f"Implement what this spec asks, including its tests. Follow the repository's "
              f"CLAUDE.md and the profile at {profile_path}. Run the suite with "
              f"`bash {script}` and leave it green. Do not commit: the loop commits.\n\n"
              f"## Spec\n\n{spec}")
    built = build(ws, task, prompt, tree)
    why = check(ws, feature, spec, tree, built, profile["suite_command"], 1)
    for round_ in range(2, 2 + REPAIRS):
        if not why:
            break
        ws.event("lean_repair", task=feature, why=why[-2000:])
        built = build(ws, task, f"{prompt}\n\n## Your last attempt failed\n\n{why}\n\n"
                      "Fix that, and keep the suite green.", tree, resume=built.session)
        why = check(ws, feature, spec, tree, built, profile["suite_command"], round_)
    if not why:
        try:
            work = lean_git.commit(repo, tree.path, tree.commit, f"feat({feature}): {feature}")
            landed = lean_git.land(repo, work, tree.commit, feature)
        except RuntimeError as error:
            why = f"it passed, but could not land on {lean_git.BRANCH}: {error}"
        else:
            ws.event("lean_merged", task=feature, commit=landed)
            tree.remove()
            return landed
    kept = tree.keep(why)
    ws.event("lean_stopped", task=feature, why=why[-2000:], tree=kept)
    mail(ws, f"graph-loop needs you: {feature}",
         f"{feature} stopped.\n\nWhy:\n{why}\n\nIts work is kept at {kept}.")
    return ""
