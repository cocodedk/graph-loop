"""One feature of the lean loop (docs/rfc/lean-loop.md): build, check, publish.

A worktree off origin/main; one builder writes the feature and its tests; the suite runs masked
(`gates.run_gate`); one reviewer reads the diff. A red suite or a refused review gets a repair with
the failure text, up to `REPAIRS`, while repairs change something and the card's budget lasts
(`lean_budget`); a model that gave no real answer gets none. Green, with a verdict: pushed as
`lean/<feature>` with a pull request carrying the findings. Otherwise the person is emailed why and
the feature stops, its worktree kept; the workspace records how it ended (`spec-<name>.json`).
"""

from __future__ import annotations

import os
import pathlib

import accounts
import gate_paths
import gates
import lean_budget
import lean_calls
import lean_diff
import lean_git
import lean_lint
import lean_spec
import providers
import review
import tools
from lean_body import builder_prompt, grill_prompt, pr_body
from lean_budget import CARD_BUDGET
from lean_judge import CODEX_BIN, judge
from lean_reason import cut
from lean_spec import lessons, record, slug
from providers import REVIEW_EFFORT  # noqa: F401 — tests read it here
from worktree import Worktree  # noqa: F401 — tests patch lean_run.Worktree

CLAUDE_BIN = os.environ.get("GRAPH_CLAUDE", "claude")
REPAIRS = 2   # repair passes after the first build; a repair often surfaces one more finding
BUILD_EFFORT = lean_calls.block("builder")["effort"]   # the block's, at import; each call reads it again
REPAIR_EFFORT = lean_calls.block("repair")["effort"]


def build(ws, task: dict, prompt: str, tree, resume: str = "",
          effort: str = providers.EFFORT) -> providers.Outcome:
    """One builder call in the worktree, at `effort`, with the builder tool set for this suite."""
    feature, account = task["id"], accounts.available()[0]
    out = providers.claude(CLAUDE_BIN, prompt, account=account, cwd=tree.path, resume=resume,
                           effort=effort, model=task.get("model", ""), allowed_tools=tools.builder_tools(task),
                           disallowed_tools=tools.builder_denies(task), budget=task.get("budget", CARD_BUDGET))
    ws.attempt(feature, account=account, kind=out.kind, cost=out.cost, tokens=out.tokens,
               effort=effort, purpose="build", turns=out.turns)
    return out


def masked(ws, command: str, cwd: str) -> tuple[bool, str]:
    """A profile command (suite or build), in the gate box: its verdict and its tail."""
    result = gates.run_gate(command, cwd, **gate_paths.options(ws.root))
    return result.passed, result.why


def grill(ws, repo: str, spec_paths: list[str], profile_path: str, earlier: str = "", final: bool = False) -> str:
    """Before anything is built: the questions only a person can answer, or ""."""
    specs = "\n\n".join(f"## {pathlib.Path(path).name}\n\n{pathlib.Path(path).read_text('utf-8')}"
                        for path in spec_paths)
    prompt = grill_prompt(profile_path, lessons(pathlib.Path(spec_paths[0]).parent), specs, earlier)

    def paid(kind, account, cost, tokens, _text):
        ws.attempt("grill", account=account, kind=kind, cost=cost, tokens=tokens,
                   effort=use["effort"], purpose="grill")
    use = lean_calls.started(ws, "grill", "grill")
    out = review.codex(CODEX_BIN, prompt, cwd=repo, effort=use["effort"], attempt=paid, job="grill")
    questions = "" if out.verdict == "ACCEPT" else (out.text or f"the grill did not answer ({out.kind})")
    ws.event("lean_grilled", verdict=out.verdict, outcome=out.kind, questions=questions[:2000], specs=[slug(p) for p in spec_paths])
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
          threads: str = "") -> tuple[str, providers.Outcome | None]:
    """Why this round is not done ("" when it is), and the reviewer's answer when it
    was asked. A revise round (`threads`, the review threads it answers) is reviewed
    like a first build, on the change it made against the branch it started from."""
    if not built.ok:
        return f"The builder did not finish ({built.kind}). Run the spec again; first read what it said: {built.text[:500]}", None
    diff = tree.diff(against=tree.commit)
    if not diff.strip():
        said = f" The last message was:\n{built.text.strip()[:1500]}" if built.text.strip() else ""
        return f"Nothing changed. Make the change the spec asks for, then run the suite.{said}", None
    if stray := lean_diff.leftovers(diff):
        return "Remove these leftover files from the change: " + ", ".join(stray), None
    passed, tail = masked(ws, command, tree.path)
    ws.event("lean_suite", task=feature, round=round_, passed=passed, tail=tail[-2000:])
    if not passed:
        return f"Fix the red suite. Run {command}, then fix the failure shown below:\n{tail}", None
    if red := lean_lint.run(ws, masked, command, tree.path, feature, round_):
        return red, None
    verdict = judge(ws, feature, spec, diff, tree.path, **({"threads": threads} if threads else {}))
    ws.event("lean_review", task=feature, round=round_, outcome=verdict.kind,
             verdict=verdict.verdict, findings=verdict.text[:1000])
    if verdict.verdict != "ACCEPT":
        return f"Fix what the reviewer refused ({verdict.kind}, {verdict.verdict}): {verdict.text}", verdict
    return "", verdict


def run_feature(ws, repo: str, spec_path: str, profile: dict, profile_path: str,
                revise: str = "", pr: str = "", open_questions: str = "") -> str:
    """One spec file, start to end. Its pull request's URL, or "" when it stopped.
    `revise` is the open pull request's review findings: fix them on its branch."""
    feature = slug(spec_path)
    spec = pathlib.Path(spec_path).read_text("utf-8")
    tree, last = lean_spec.start(repo, feature, lean_spec.state(ws, spec_path), revise)
    ws.event("lean_feature_started", task=feature, spec=str(spec_path), base=tree.commit,
             tree=tree.path, resumed=bool(last))
    own = lean_spec.card_gate(spec)
    task = {"id": feature, "gate": own or profile["suite_command"], "budget": CARD_BUDGET}
    script = tools.write_gate_script(task)   # the builder may run it: `bash <script>`
    suite = lean_lint.Commands(profile["suite_command"], profile.get("lint_command", ""))
    prompt = builder_prompt(spec, script, profile_path, lessons(pathlib.Path(spec_path).parent), bool(own),
                            open_questions, suite.lint)
    use = lean_calls.started(ws, "builder", feature)
    built = build(ws, {**task, "model": use["model"]}, f"{prompt}\n\n## Your last attempt failed\n\n{last}\n\n"
                  "The work so far is in this checkout: fix that, and keep the suite green." if last else prompt,
                  tree, effort=use["effort"])
    spent = lean_budget.after(ws, task, built, 0.0, False)
    why, verdict = check(ws, feature, spec, tree, built, suite, 1, revise)
    for round_ in range(2, 2 + REPAIRS):
        # Only a real answer is worth a repair (`Outcome.consumes_attempt`); a limit, a crash, a repair that
        # changed nothing or a card that spent its budget stops the run, its rounds kept.
        if not why or not built.ok or (verdict is not None and not verdict.ok):
            break
        if spent >= CARD_BUDGET:                   # planned wrongly: no repair, stop and say so
            why = f"{lean_budget.stopped_words(spent)}\n\n{why}"
            break
        ws.event("lean_repair", task=feature, why=cut(why))
        before = tree.diff(binary=True, against=tree.commit)
        use = lean_calls.started(ws, "repair", feature)
        resumed = bool(built.session)
        built = build(ws, {**task, "model": use["model"]}, f"{prompt}\n\n## Your last attempt failed\n\n{why}\n\n"
                      "Fix that, and keep the suite green." + (" Keep your list of choices complete." if open_questions
                                                                else ""), tree, resume=built.session,
                      effort=use["effort"])
        spent = lean_budget.after(ws, task, built, spent, resumed)
        if built.ok and tree.diff(binary=True, against=tree.commit) == before:
            why = f"The repair changed nothing. Read what the builder said, then change the code or the spec:\n{built.text[:1500]}\n\n{why}"
            break
        why, verdict = check(ws, feature, spec, tree, built, suite, round_, revise)
    # Findings are the reviewer's text unless the parser reads that text as its answer. Green, and
    # accepted or still refused for named findings after the last repair: published. Else it stops.
    found = "" if verdict is None or review._read_review(verdict.text)[0] else verdict.text.strip()
    if not why or (verdict is not None and verdict.verdict == "REJECT" and found):
        try:
            title = f"feat({feature}): {feature}"
            work = lean_git.commit(repo, tree.path, tree.commit, title)
            url = lean_git.update(repo, work, feature, pr, found if why else "") if revise else (
                lean_git.publish(repo, work, feature, title,
                                 pr_body(spec_path, why, found, open_questions, built.text)))
        except RuntimeError as error:
            why = f"It passed, but could not open its pull request. Fix this, then run the spec again: {error}\n\n{why}".strip()
        else:
            ws.event("lean_published", task=feature, commit=work, pr=url)
            record(ws, spec_path, lean_status="pr_open", lean_pr=url, lean_rounds=None, lean_asked=None)
            try:
                tree.remove()
            except OSError as error:   # files a suite's container left as root: tidy later
                ws.event("lean_tree_left", task=feature, tree=tree.path, error=str(error)[:300])
            return url
    kept = tree.keep(why)
    if not revise:                   # a revision that stopped leaves its pull request open
        record(ws, spec_path, lean_status="stopped", lean_worktree=kept, lean_rounds=None, lean_asked=None)
    ws.event("lean_stopped", task=feature, why=cut(why), tree=kept)
    mail(ws, f"graph-loop needs you: {feature}",
         f"{feature} stopped.\n\nWhy:\n{why}\n\nIts work is kept at {kept}."
         + (lean_budget.review_note(spec_path) if built.kind == "budget" or spent >= CARD_BUDGET else ""))
    return ""
