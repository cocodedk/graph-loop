#!/usr/bin/env python3
"""Turn one project brief into the branch goals a campaign is planned from.

The layer above the speccer. The speccer turns ONE goal into one spec and the
slicer turns specs into cards, so both need something approved to exist before
they can read anything. Nothing turned "a software project" into that first set
of goals; this does, and then it stops.

A branch is a capability a person would name, and there is one test for where
its boundary is: **can this branch's acceptance be observed with the other
branches absent?** If yes it is a branch; if no it belongs to the branch beside
it. That is the gate rule one level up, and it is the only rule this needs.

It writes acceptance in words and never a gate. The slicer derives gates from
acceptance and the drive loop still proves every gate red before anyone builds.

Standalone, like the speccer: no service stands behind it, and `NEEDS_PERSON`
is a terminal gap rather than a queue — the brief does not support a branching,
and whoever ran this reads the reason.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "drive" / "lib"))

import cardfile  # type: ignore[import-not-found]
from contracts import mapping, safe_name
from intelligence import ask, review
from repair import ROUNDS, Unreachable, repaired
from review_scope import VERDICT  # type: ignore[import-not-found]

TOP = {"result", "reason", "branches"}
BRANCH = {"name", "goal", "acceptance"}


def prompt(brief: str, repo: pathlib.Path) -> str:
    return (
        "Read the repository, then turn this brief into the branches a campaign will be "
        "planned from. A branch is one capability a person would name. Split them so that "
        "each branch's acceptance can be observed with every other branch absent; anything "
        "that cannot be is part of the branch beside it. State only what the brief and the "
        "repository support, in plain language. Write acceptance in words, never a command "
        "and never a test. Do not write code and do not plan the work inside a branch.\n\n"
        f"Brief:\n{brief}\n\nRepository: {repo}\n\n"
        "Answer with YAML only and exactly: result (BRANCHES or NEEDS_PERSON), reason, "
        "branches. BRANCHES requires a list of {name: safe-slug, goal: one sentence, "
        "acceptance: what someone would observe}. NEEDS_PERSON requires branches: null.")


def write_answer(text: str, *, brief: str, vault: pathlib.Path,
                 reviewer=None, repo: pathlib.Path | None = None) -> tuple[str, object]:
    """One reviewed branching, written as notes, or the reason there is none."""
    answer = mapping(text)
    if set(answer) != TOP or answer.get("result") not in ("BRANCHES", "NEEDS_PERSON") \
            or not isinstance(answer.get("reason"), str):
        raise ValueError("the branch answer has the wrong closed shape")
    if answer["result"] == "NEEDS_PERSON":
        if answer.get("branches") is not None:
            raise ValueError("NEEDS_PERSON requires branches: null")
        return "needs_person", answer["reason"]
    branches = answer.get("branches")
    if not isinstance(branches, list) or not branches:
        raise ValueError("BRANCHES requires at least one branch")
    for one in branches:
        if not isinstance(one, dict) or set(one) != BRANCH:
            raise ValueError("a branch is exactly name, goal and acceptance")
        safe_name(one["name"], "branch name")
        for key in ("goal", "acceptance"):
            if not isinstance(one[key], str) or not one[key].strip():
                raise ValueError(f"a branch's {key} must say something")
    judge = reviewer or (lambda question: review(question, repo))
    verdict = judge(
        "Review this proposed branching independently. Take the branches ONE AT A TIME, "
        "in the order given, and for each one answer in your own head: with every other "
        "branch deleted, what would a person see this branch do? A branch whose only "
        "consequence is that a later branch can run — an input step, a fetch nobody reads, "
        "a hand-off — fails that and belongs to the branch beside it. Say which branch it "
        "belongs to. Then refuse invented facts the brief and repository do not support, "
        "two capabilities in one branch, and any authority the brief does not grant. "
        "Fewer branches is better when the test allows it. "
        + VERDICT + "\n\n"
        f"Repository to inspect: {repo.resolve() if repo else 'not supplied'}\n"
        f"Brief:\n{brief}\n\nBranching:\n" +
        "\n".join(f"- {one['name']}: {one['goal']} — observed by: {one['acceptance']}"
                  for one in branches))
    if not verdict.ok:
        return "review_refused", verdict.why
    return "written", _notes(vault, branches)


def _notes(vault: pathlib.Path, branches: list[dict]) -> list[pathlib.Path]:
    """One note per branch, numbered so the vault's sidebar reads in order.

    Whole or not at all: a half-written branching is a graph nobody planned.
    """
    vault.mkdir(parents=True, exist_ok=True)
    written = []
    for order, one in enumerate(branches, start=1):
        path = vault / f"{order:02d}-{one['name']}{cardfile.SUFFIX}"
        if path.exists():
            raise FileExistsError(f"branch {path} already exists")
        written.append(path)
    for path, one in zip(written, branches, strict=True):
        path.write_text(cardfile.dump(
            {"status": "branch", "goal": one["goal"], "why": one["acceptance"]}), "utf-8")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=pathlib.Path, required=True)
    parser.add_argument("--repo", type=pathlib.Path, required=True)
    parser.add_argument("--vault", type=pathlib.Path, required=True,
                        help="where the branch notes are written, inside --repo")
    parser.add_argument("--answer", type=pathlib.Path)
    args = parser.parse_args(argv)
    repo, vault = args.repo.resolve(), args.vault.resolve()
    if not vault.is_relative_to(repo):
        parser.error("--vault must be inside --repo")
    brief = args.brief.read_text("utf-8")
    question = prompt(brief, repo)
    canned = [args.answer.read_text("utf-8")] if args.answer else []

    def ask_once(asked: str) -> str:
        if canned:
            return canned.pop(0)
        planned = ask(asked, repo)
        if not planned.ok:
            raise Unreachable(str(planned.why))
        return planned.text

    try:
        # One malformed answer used to throw the whole layer away, paid planner
        # call and all; the slicer has had a repair round since it was written.
        state, detail = repaired(question, ask_once,
                                 lambda answer: write_answer(answer, brief=brief,
                                                             vault=vault, repo=repo),
                                 rounds=1 if args.answer else ROUNDS)
    except Unreachable as down:
        print(str(down), file=sys.stderr); return 2
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr); return 2
    if state == "written":
        print("\n".join(str(path) for path in detail))     # type: ignore[arg-type]
        return 0
    print(f"{state}: {detail}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
