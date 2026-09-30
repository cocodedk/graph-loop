"""One feature of the lean loop (docs/rfc/lean-loop.md): build, check, publish.

A worktree off origin/main; one builder writes the feature and its tests; the suite runs masked
(`gates.run_gate`); one reviewer reads the diff. A red suite or a refused review gets a repair with
the failure text, up to `REPAIRS`, while repairs change something and the card's budget lasts
(`lean_budget`); a model that gave no real answer gets none. Green, with a verdict: pushed as
`lean/<feature>` with a pull request carrying the findings. Otherwise the person is emailed why and
the feature stops, its worktree kept; the spec's front matter records how it ended.
"""

from __future__ import annotations

import os
import pathlib

import accounts
import gate_paths
import gates
import lean_budget
import lean_diff
import lean_git
import lean_spec
import providers
import review
import tools
from lean_body import builder_prompt, grill_prompt, pr_body
from lean_budget import CARD_BUDGET
from lean_spec import lessons, record, slug
from providers import REVIEW_EFFORT  # the one review effort, for both loops
from review_scope import VERDICT
from worktree import Worktree  # noqa: F401 — tests patch lean_run.Worktree

CLAUDE_BIN = os.environ.get("GRAPH_CLAUDE", "claude")
CODEX_BIN = os.environ.get("GRAPH_CODEX", "codex")
REPAIRS = 2   # repair passes after the first build; a repair often surfaces one more finding
BUILD_EFFORT = "high"   # 2026-09-28 benchmark: Sonnet 5.5 at medium was still refused after two repairs
REPAIR_EFFORT = "high"   # a repair round is handed why the last one fell short (2026-09-26 trial)


def build(ws, task: dict, prompt: str, tree, resume: str = "",
          effort: str = providers.EFFORT) -> providers.Outcome:
    """One builder call in the worktree, at `effort`, with the builder tool set for this suite."""
    feature, account = task["id"], accounts.available()[0]
    out = providers.claude(CLAUDE_BIN, prompt, account=account, cwd=tree.path, resume=resume,
                           effort=effort, allowed_tools=tools.builder_tools(task),
                           disallowed_tools=tools.builder_denies(task), budget=task.get("budget", CARD_BUDGET))
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
              f"acceptance tests name that does not hold, any defect you can name (wrong for some "
              f"real input or use), a security hole, behaviour added without tests, or a file the spec "
              f"does not call for that nothing uses (name it). Accept, listing findings, only for "
              f"style, a stated limit or a suggestion. In this review an ACCEPT may carry findings, "
              f"whatever the answer rule below says.\n\n"
              f"## Spec\n\n{spec}\n\n## The diff against main\n\n{diff}\n\n{VERDICT}")

    def paid(kind, account, cost, tokens, _text):
        ws.attempt(feature, account=account, kind=kind, cost=cost, tokens=tokens,
                   effort=REVIEW_EFFORT, purpose="review")
    ws.event("lean_call_started", purpose="review", task=feature, effort=REVIEW_EFFORT)
    return review.codex(CODEX_BIN, prompt, cwd=cwd, effort=REVIEW_EFFORT, attempt=paid)


def grill(ws, repo: str, spec_paths: list[str], profile_path: str, earlier: str = "", final: bool = False) -> str:
    """Before anything is built: the questions only a person can answer, or ""."""
    specs = "\n\n".join(f"## {pathlib.Path(path).name}\n\n{pathlib.Path(path).read_text('utf-8')}"
                        for path in spec_paths)
    prompt = grill_prompt(profile_path, lessons(pathlib.Path(spec_paths[0]).parent), specs, earlier)

    def paid(kind, account, cost, tokens, _text):
        ws.attempt("grill", account=account, kind=kind, cost=cost, tokens=tokens,
                   effort=REVIEW_EFFORT, purpose="grill")
    ws.event("lean_call_started", purpose="grill", task="grill", effort=REVIEW_EFFORT)
    out = review.codex(CODEX_BIN, prompt, cwd=repo, effort=REVIEW_EFFORT, attempt=paid)
    questions = "" if out.verdict == "ACCEPT" else (out.text or f"the grill did not answer ({out.kind})")
    ws.event("lean_grilled", verdict=out.verdict, outcome=out.kind, questions=questions[:2000])
    if questions and final and out.verdict == "REJECT":   # the round limit: the run goes on
        mail(ws, "graph-loop is building with open questions", f"{questions}\n\nThe round limit is reached: "
             "building goes on with these unresolved. The builder decides each, and its choices go in the pull "
             "request description. No answer is needed to continue.")
    elif questions:
        subject = ("graph-loop has questions before building" if out.verdict
                   else "graph-loop could not read the specs before building")
        mail(ws, subject, f"{questions}\n\nAnswer them in the specs, then run again. Nothing was built.")
    return questions


def mail(ws, subject: str, body: str) -> None:
    """Through the proven contact; a failed send is logged, never raised."""
    ws.mail_person(subject, body)


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
    if stray := lean_diff.leftovers(diff):
        return "the change carries leftover files, remove them: " + ", ".join(stray), None
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


def run_feature(ws, repo: str, spec_path: str, profile: dict, profile_path: str,
                revise: str = "", pr: str = "", open_questions: str = "") -> str:
    """One spec file, start to end. Its pull request's URL, or "" when it stopped.
    `revise` is the open pull request's review findings: fix them on its branch."""
    feature = slug(spec_path)
    spec = pathlib.Path(spec_path).read_text("utf-8")
    tree, last = lean_spec.start(repo, feature, spec, revise)
    ws.event("lean_feature_started", task=feature, spec=str(spec_path), base=tree.commit,
             tree=tree.path, resumed=bool(last))
    own = lean_spec.card_gate(spec)
    task = {"id": feature, "gate": own or profile["suite_command"], "budget": CARD_BUDGET}
    script = tools.write_gate_script(task)   # the builder may run it: `bash <script>`
    prompt = builder_prompt(spec, script, profile_path, lessons(pathlib.Path(spec_path).parent), bool(own),
                            open_questions)
    ws.event("lean_call_started", purpose="build", task=feature, effort=BUILD_EFFORT)
    built = build(ws, task, f"{prompt}\n\n## Your last attempt failed\n\n{last}\n\nThe work so far is "
                  "in this checkout: fix that, and keep the suite green." if last else prompt, tree,
                  effort=BUILD_EFFORT)
    spent = lean_budget.after(ws, task, built, 0.0, False)
    why, verdict = check(ws, feature, spec, tree, built, profile["suite_command"], 1, bool(revise))
    for round_ in range(2, 2 + REPAIRS):
        # Only a real answer is worth a repair (`Outcome.consumes_attempt`); a limit, a crash, a repair that
        # changed nothing or a card that spent its budget stops the run, its rounds kept.
        if not why or not built.ok or (verdict is not None and not verdict.ok):
            break
        if spent >= CARD_BUDGET:                   # planned wrongly: no repair, stop and say so
            why = f"{lean_budget.stopped_words(spent)}\n\n{why}"
            break
        ws.event("lean_repair", task=feature, why=why[-2000:])
        before = tree.diff(binary=True, against=tree.commit)
        ws.event("lean_call_started", purpose="build", task=feature, effort=REPAIR_EFFORT)
        resumed = bool(built.session)
        built = build(ws, task, f"{prompt}\n\n## Your last attempt failed\n\n{why}\n\n"
                      "Fix that, and keep the suite green." + (" Keep your list of choices complete." if open_questions
                                                                else ""), tree, resume=built.session,
                      effort=REPAIR_EFFORT)
        spent = lean_budget.after(ws, task, built, spent, resumed)
        if built.ok and tree.diff(binary=True, against=tree.commit) == before:
            why = f"the repair changed nothing. The builder said:\n{built.text[:1500]}\n\n{why}"
            break
        why, verdict = check(ws, feature, spec, tree, built, profile["suite_command"], round_,
                             bool(revise))
    # Findings are the reviewer's text unless the parser reads that text as its answer (a
    # reply with none keeps its answer as its text). Green, and accepted or still refused
    # for named findings after the last repair: published with them. Else it stops below.
    found = "" if verdict is None or review._read_review(verdict.text)[0] else verdict.text.strip()
    if not why or (verdict is not None and verdict.verdict == "REJECT" and found):
        try:
            title = f"feat({feature}): {feature}"
            work = lean_git.commit(repo, tree.path, tree.commit, title)
            url = lean_git.update(repo, work, feature, pr) if revise else lean_git.publish(
                repo, work, feature, title, pr_body(spec_path, why, found, open_questions, built.text))
        except RuntimeError as error:
            why = f"it passed, but could not open its pull request: {error}\n\n{why}".strip()
        else:
            ws.event("lean_published", task=feature, commit=work, pr=url)
            record(spec_path, lean_status="pr_open", lean_pr=url, lean_rounds=None, lean_asked=None)
            try:
                tree.remove()
            except OSError as error:   # files a suite's container left as root: tidy later
                ws.event("lean_tree_left", task=feature, tree=tree.path, error=str(error)[:300])
            return url
    kept = tree.keep(why)
    if not revise:                   # a revision that stopped leaves its pull request open
        record(spec_path, lean_status="stopped", lean_worktree=kept, lean_rounds=None, lean_asked=None)
    ws.event("lean_stopped", task=feature, why=why[-2000:], tree=kept)
    mail(ws, f"graph-loop needs you: {feature}",
         f"{feature} stopped.\n\nWhy:\n{why}\n\nIts work is kept at {kept}."
         + (lean_budget.review_note(spec_path) if built.kind == "budget" or spent >= CARD_BUDGET else ""))
    return ""
