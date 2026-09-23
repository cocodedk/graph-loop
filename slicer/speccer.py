#!/usr/bin/env python3
"""Turn one approved goal into one small, independently reviewed source spec.

Standalone: the driver never calls this, and no service stands behind it. Its
`needs_person` result is therefore a TERMINAL GAP, not a queue — it says the
goal cannot be specced from what the repository declares, and whoever ran this
by hand reads the reason. Nothing in the loop waits for it (astra's section G,
the owner's order of 2026-09-08).
"""

from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "graph" / "lib"))

import cardfile  # type: ignore[import-not-found]
from contracts import mapping, safe_name
from intelligence import ask, review
from repair import ROUNDS, Unreachable, repaired
from review_scope import VERDICT  # type: ignore[import-not-found]
from slicer_state import record

TOP = {"result", "reason", "spec"}
SECTIONS = ("## Goal", "## Acceptance", "## Boundaries")


def prompt(goal: str, repo: pathlib.Path) -> str:
    return (
        "Read the repository before turning this goal into one small source specification. "
        "State only what the goal and repository support. Use plain language. Acceptance must "
        "be observable and boundaries must say what is not granted. Do not add a required "
        "method that acceptance cannot observe. Do not write code.\n\n"
        "A plan never gives work to a person. Work that a person judges is still the loop's to build: "
        'its gate is "it builds and every existing test stays green", and the person accepts the result '
        "at the end; judgement is never a reason to cut no card. What only a person can supply "
        "(a file the loop cannot fetch, a credential, a decision) is asked before any card is cut: "
        "answer NEEDS_PERSON first, naming it, and plan nothing further until it is answered.\n\n"
        f"Goal: {goal}\nRepository: {repo}\n\n"
        "Answer with YAML only and exactly: result (SPEC or NEEDS_PERSON), reason, spec. "
        "SPEC requires spec: {name: safe-slug, body: markdown}. The Markdown must contain "
        "## Goal, ## Acceptance and ## Boundaries. NEEDS_PERSON requires spec: null.")


def write_answer(text: str, *, goal: str, spec_root: pathlib.Path,
                 reviewer=None, repo: pathlib.Path | None = None,
                 branch: str = "") -> tuple[str, pathlib.Path | str]:
    answer = mapping(text)
    if set(answer) != TOP or answer.get("result") not in ("SPEC", "NEEDS_PERSON") \
            or not isinstance(answer.get("reason"), str):
        raise ValueError("the speccer answer has the wrong closed shape")
    if answer["result"] == "NEEDS_PERSON":
        if answer.get("spec") is not None:
            raise ValueError("NEEDS_PERSON requires spec: null")
        return "needs_person", answer["reason"]
    spec = answer.get("spec")
    if not isinstance(spec, dict) or set(spec) != {"name", "body"}:
        raise ValueError("SPEC requires only name and body")
    name = safe_name(spec.get("name"), "spec name")
    body = spec.get("body")
    if not isinstance(body, str) or any(section not in body for section in SECTIONS):
        raise ValueError("the spec must contain Goal, Acceptance and Boundaries sections")
    if cardfile.FRONT.match(body.lstrip()):
        # The body is the spec's PROSE; this function writes the note head above
        # it. A model that answers with a whole note gave the file two `---`
        # blocks and two `## Needs`, and `cardfile.parse` then matched the first
        # head and read the second as prose. Three of six specs came out that way
        # on the first real run (2026-09-18). Refused rather than stripped: the
        # second head carries fields nobody asked for, and the repair round below
        # is how the model is told.
        raise ValueError("the spec body is a whole note: give the prose alone, no front matter")
    judge = reviewer or (lambda question: review(question, repo))
    verdict = judge(
        "Review this proposed source spec independently. Refuse invented facts, unclear "
        "acceptance, an unobservable required method, more than one idea, or authority not "
        "granted by the goal. " + VERDICT + "\n\n"
        f"Repository to inspect: {repo.resolve() if repo else 'not supplied'}\n"
        f"Goal: {goal}\n\nSpec:\n{body}")
    if not verdict.ok:
        return "review_refused", verdict.why
    spec_root.mkdir(parents=True, exist_ok=True)
    final = spec_root / f"{name}.md"
    if final.exists():
        raise FileExistsError(f"spec {final} already exists")
    # A note, not loose Markdown: the spec sits in the same vault as the cards
    # cut from it, and `branch` is the wikilink back to the goal it specs — the
    # graph has no root without it.
    head = cardfile.dump({"status": "spec", **({"needs": [branch]} if branch else {})})
    beside = final.with_suffix(".md.new")
    beside.write_text(f"{head}\n{body.rstrip()}\n", "utf-8")
    beside.replace(final)
    return "written", final


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--repo", type=pathlib.Path, required=True)
    parser.add_argument("--spec-root", type=pathlib.Path, required=True)
    parser.add_argument("--branch", default="",
                        help="the branch note this spec is for, as its path in the vault")
    parser.add_argument("--campaign", default="",
                        help="campaign dir: where prompts and answers are kept, so a\n"
                             "retry does not read its own refused answer back")
    parser.add_argument("--answer", type=pathlib.Path)
    args = parser.parse_args(argv)
    repo, root = args.repo.resolve(), args.spec_root.resolve()
    if not root.is_relative_to(repo):
        parser.error("--spec-root must be inside --repo")
    question = prompt(args.goal, repo)
    canned = [args.answer.read_text("utf-8")] if args.answer else []
    calls_root = pathlib.Path(args.campaign) if args.campaign else repo

    def ask_once(asked: str) -> str:
        if canned:
            answer = canned.pop(0)
        else:
            planned = ask(asked, repo)
            if not planned.ok:
                raise Unreachable(str(planned.why))
            answer = planned.text
        record(calls_root, asked, answer, ".speccer-calls")
        return answer

    try:
        # A repair round, as the slicer has: one malformed answer from the
        # planner or its reviewer used to throw a paid call away.
        state, detail = repaired(question, ask_once,
                                 lambda answer: write_answer(answer, goal=args.goal,
                                                             spec_root=root, repo=repo,
                                                             branch=args.branch),
                                 rounds=1 if args.answer else ROUNDS)
    except Unreachable as down:
        print(str(down), file=sys.stderr); return 2
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr); return 2
    print(f"{state}: {detail}")
    return 0 if state == "written" else 2


if __name__ == "__main__":
    raise SystemExit(main())
