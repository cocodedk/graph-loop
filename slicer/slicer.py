#!/usr/bin/env python3
"""Turn approved specs into one molecule, or re-slice one parked CODE leaf."""

from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
DRIVE_LIB = HERE.parent / "drive" / "lib"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(DRIVE_LIB))

from asking import prompt
from backlog import Backlog  # type: ignore[import-not-found]
from intelligence import ask
from repair import AGAIN, REPAIRABLE
from slicer_answer import run_answer  # this file stays the one door for it
from slicer_law import assert_wall
from slicer_state import covered, digest, forget, inside, record, trace
from tree import CardMoved, recover


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=pathlib.Path, required=True)
    parser.add_argument("--backlog", type=pathlib.Path, required=True)
    parser.add_argument("--source", type=pathlib.Path, action="append", required=True)
    parser.add_argument("--target", default="")
    parser.add_argument("--goal", default="", help="the campaign's own goal, recorded at init")
    parser.add_argument("--campaign", default="", help="campaign dir: every model call lands in its ledger")
    parser.add_argument("--evidence", type=pathlib.Path, action="append", default=[])
    parser.add_argument("--answer", type=pathlib.Path)
    args = parser.parse_args(argv)
    repo, backlog = args.repo.resolve(), args.backlog.resolve()
    sources = [(repo / path).resolve() if not path.is_absolute() else path.resolve()
               for path in args.source]
    evidence = [(repo / path).resolve() if not path.is_absolute() else path.resolve()
                for path in args.evidence]
    try:
        inside(repo, sources, "approved source")
    except ValueError as error:
        # An approved source that is gone makes an accepted coverage OF it a
        # claim about nothing, and this runs before the record is ever read.
        forget(backlog)
        print(str(error), file=sys.stderr); return 2
    try:
        inside(repo, evidence, "failure evidence")
    except ValueError as error:
        print(str(error), file=sys.stderr); return 2
    try:
        source_digest = digest(sources, repo)
    except (OSError, ValueError):
        source_digest = "(unreadable)"
    trace(backlog, "start", repo=str(repo), target=args.target or "(source gap)",
          sources=[str(s) for s in sources], source_digest=source_digest,
          evidence=[str(e) for e in evidence])
    rows = Backlog(backlog).tasks()
    target = next((row for row in rows if row.get("id") == args.target), None)
    if args.target and target is None:
        print(f"no task {args.target} in {backlog}", file=sys.stderr); return 2
    if args.campaign:
        # BEFORE recovery, not after it. `recover` publishes, and a publish
        # asks the campaign's claims file whether a lane is building this card
        # (`tree_stale.being_built`). Set further down, as it was, recovery had no
        # campaign to ask and settled a card a builder was holding.
        import intelligence
        intelligence.CAMPAIGN = pathlib.Path(args.campaign)
    # Prompts and answers go beside the CAMPAIGN, never inside the repository
    # the planner is told to read, or a retry finds its own refused answer and
    # reuses it (`slicer_state.record`). With no campaign there is nowhere else.
    calls_root = pathlib.Path(args.campaign) if args.campaign else backlog
    if target is not None:
        try:
            assert_wall(target)
            recovered, retired = recover(backlog, args.target)
        except CardMoved as moved:
            # the same uncharged refusal the planned publish gets: nobody judged
            # this card as it now stands, and a builder holds it
            trace(backlog, "card_moved", why=str(moved)[:300])
            print(f"card_moved: {moved}", file=sys.stderr); return 2
        except (OSError, ValueError) as error:
            print(str(error), file=sys.stderr); return 2
        if retired:
            # Kept whole under that name, and out of the reader's way: this
            # turn plans the parent afresh rather than refusing it again. Read
            # again before anything is planned — the rows above still hold the
            # retired child and the wait the parent had on it, and a planner
            # shown a card that is gone plans around it (Codex, finding 5).
            trace(backlog, "stale_child_retired", kept=retired)
            print(f"stale_child_retired: {retired}")
            rows = Backlog(backlog).tasks()
            target = next((row for row in rows if row.get("id") == args.target), None)
            if target is None:
                print(f"no task {args.target} in {backlog}", file=sys.stderr); return 2
        if recovered:
            trace(backlog, "roll_forward_recovered", child=str(recovered))
            print(f"recovered: {recovered}")
            return 0
        trace(backlog, "wall_asserted", target=args.target)
    if not args.target and covered(backlog, sources, repo, rows):
        trace(backlog, "covered_no_gap")
        print("covered: approved sources are unchanged")
        return 0
    try:
        question = prompt(repo, sources, rows, target, evidence)
    except ValueError as error:
        print(f"planning_refused: {error}")
        return 2
    if args.goal:
        question = f"The campaign's goal: {args.goal}\n\n" + question
    trace(backlog, "prompt_built", chars=len(question), tasks_shown=len(rows))
    if args.answer:
        answers = [args.answer.read_text("utf-8")]
    else:
        answers = []
    for repair in range(3):
        if answers:
            answer = answers.pop(0)
        else:
            trace(backlog, "planner_call", attempt=repair + 1)
            planned = ask(question, repo)
            if not planned.ok:
                trace(backlog, "planner_refused", attempt=repair + 1, why=str(planned.why)[:300])
                print(f"planner_unavailable: {planned.why}", file=sys.stderr); return 2
            answer = planned.text
            trace(backlog, "planner_answered", attempt=repair + 1, chars=len(answer))
        record(calls_root, question, answer)
        trace(backlog, "answer_recorded", attempt=repair + 1)
        try:
            state, detail = run_answer(answer, repo=repo, backlog=backlog,
                                       sources=sources, target_id=args.target,
                                       started=target)
        except CardMoved as moved:
            # A person decided while this planned: the molecule was planned
            # against the older card. Nothing is written and nothing is
            # charged — `slice_outcome.UNANSWERED` carries the same name.
            trace(backlog, "card_moved", why=str(moved)[:300])
            print(f"card_moved: {moved}", file=sys.stderr); return 2
        except ValueError as error:
            trace(backlog, "validator_refused", attempt=repair + 1, why=str(error)[:300],
                  final=bool(args.answer or repair == 2))
            if args.answer or repair == 2:
                print(f"validation_refused: {error}", file=sys.stderr); return 2
            question += "\n\nThe validator refused that answer: " + str(error) + AGAIN
            continue
        except (KeyError, OSError) as error:
            print(str(error), file=sys.stderr); return 2
        if state in REPAIRABLE and not args.answer and repair < 2:
            # The same round a bad shape gets. An independent reviewer read this
            # answer and said what was wrong with it; that is the one thing the
            # planner can act on, and it used to be printed and dropped.
            trace(backlog, "review_refused", attempt=repair + 1, state=state,
                  why=str(detail)[:300])
            question += f"\n\nAn independent reviewer refused that answer: {detail}" + AGAIN
            continue
        trace(backlog, "ended", state=state, detail=str(detail)[:200])
        print(f"{state}: {detail}")
        return 0 if state in ("published", "covered") else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
