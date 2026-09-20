"""The driver's commands other than `run`, and the two real providers.

`graph-goal.py` keeps `run` — the loop that works the backlog — and the command
line; everything a person calls once (init, approve, status, doctor, report,
stop) lives here, with the constants both files share.
"""

from __future__ import annotations

import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import where
from backlog import Backlog
from campaign_of import backlog_of
from doctor import as_text as doctor_text
from doctor import diagnose
from keep_branch import campaign_branch
from plan_phase import command_plan  # noqa: F401 — the plan phase's door stays here
from providers import claude, codex
from report import as_text, report
from turn import (  # noqa: F401 — the door stays here
    plan_with_claude,
    replan_pending,
    run_lanes,
    stood_down,
    taking_now,
    turn_opens,
)
from workspace import Workspace

REPO = where.repo()
DEFAULT_WORKSPACE = where.campaign()
CLAUDE_BIN = os.environ.get("GRAPH_CLAUDE", "claude")
CODEX_BIN = os.environ.get("GRAPH_CODEX", "codex")
# What a builder may run lives in lib/tools.py: a code task gets a shell, a
# live task gets only the helper. BUILDER_TOOLS is the code task's list.
from tools import builder_tools

BUILDER_TOOLS = builder_tools({})


def _space(args) -> Workspace:
    return Workspace(args.workspace or DEFAULT_WORKSPACE)


def _real_build(prompt, *, account, cwd, files, tools, denies, guard, effort="", resume="",
                model=""):
    """One builder call, in the task's own worktree, with the tools the task
    allows (lib/tools.py): a live task's builder has no shell, only the helper.
    `resume` continues the previous round's session — the same work, so what it
    already read is not paid for twice."""
    return claude(CLAUDE_BIN, prompt, account=account, model=model, cwd=cwd, effort=effort,
                  resume=resume,
                  allowed_tools=tools, disallowed_tools=denies, guard=guard,
                  guard_files="\n".join(str(pathlib.Path(cwd) / f) for f in files) if guard else "")


def _real_review(prompt, *, cwd="", effort="", space=None, task_id=""):
    # `cwd` is the worktree the diff or contract belongs to — never the
    # driver's own checkout, or the reviewer reads the wrong tree.
    # `space`/`task_id` default to nothing so a caller that only wants a
    # verdict (a test, a one-off check) is not made to fake a workspace. The
    # loop's two call sites (loop_contract.py, loop_judge.py) pass both, so
    # every belt member codex() asks — refusals included, the same as a
    # build's per-account record (lib/loop_steps.py) — lands in the campaign
    # ledger under the task this review belongs to, tagged purpose="review"
    # so report.py can tell review spend apart from a build's.
    def record(kind, account, cost, tokens, text):
        space.attempt(task_id, account=account, kind=kind, cost=cost, tokens=tokens,
                      purpose="review")
    return codex(CODEX_BIN, prompt, effort=effort, cwd=cwd,
                attempt=record if space is not None and task_id else None)


def command_init(args) -> int:
    book = Backlog(args.backlog)
    branch = campaign_branch(str(REPO), args.branch or where.branch())
    space = _space(args).init(goal=args.goal or "the backlog", backlog=str(book.path),
                              branch=branch)
    declare_sources(space, list(getattr(args, "source", None) or []))
    (space.root / "approved").unlink(missing_ok=True)
    # What the campaign RECORDS, never what this call asked for. An init that
    # finds an existing campaign changes nothing, and printing the argument
    # back read as confirmation that it had been recorded.
    kept = Backlog(backlog_of(space))
    print(f"campaign at {space.root}\nbacklog {kept.path} — {len(kept.tasks())} tasks")
    if kept.path != book.path:
        print(f"this campaign already existed: it still points at {kept.path}, "
              f"not at {book.path}")
    print("nothing runs until: graph-goal.py approve")
    return 0


def declare_sources(space, paths: list[str]) -> list[str]:
    """Validated, repo-relative approved sources, recorded on the campaign.
    Shared by `init --source` and the `sources` command, so an existing
    campaign can declare or move its sources without a new init."""
    good = []
    root = pathlib.Path(REPO).resolve()
    for raw in paths:
        path = pathlib.Path(raw)
        if path.is_absolute():
            raise SystemExit(f"{raw}: an approved source is repo-relative, never absolute")
        real = (root / path).resolve()   # a `..` or a symlink resolves out loud
        if not real.exists():
            raise SystemExit(f"{raw}: not in the repository")
        try:
            good.append(str(real.relative_to(root)))
        except ValueError:
            raise SystemExit(f"{raw}: escapes the repository") from None
    if good:
        space.event("sources_declared", sources=good)
    return good


def command_sources(args) -> int:
    space = _space(args)
    good = declare_sources(space, args.source)
    print(f"approved sources recorded: {', '.join(good) or 'none'}")
    return 0



def command_approve(args) -> int:
    space = _space(args)
    (space.root / "approved").write_text("approved\n", "utf-8")
    space.event("approved")
    print("approved — `run` will now start tasks")
    return 0


def command_status(args) -> int:
    space = _space(args)
    rows = space.events()
    book = Backlog(_backlog_of(space))
    done = [row for row in book.tasks() if row.get("status") == "done"]
    print(f"campaign {space.root}")
    print(f"  approved: {(space.root / 'approved').exists()}   stopping: {space.stopping()}")
    print(f"  tasks: {len(done)} done of {len(book.tasks())}")
    running = space.running()
    print(f"  running: {', '.join(running) or 'nothing'}")
    held = [row['id'] for row in book.waiting_for_human()]
    if held:
        # The hold stays on the card as stored evidence; nothing takes it off
        # but a person, and the campaign ends naming it.
        print(f"  held on the card: {', '.join(held)}")
    ready = [row["id"] for row in book.startable(running=list(running))]
    print(f"  ready now: {', '.join(ready) or 'nothing'}")
    out = report(space)
    print(f"  attempts recorded: {sum(1 for r in rows if r.get('kind') == 'attempt')}"
          f"   known spend: ${out['spend_known']:.2f}")
    if out["review_spend_known"] or out["review_calls_unknown_cost"]:
        print(f"  reviews: ${out['review_spend_known']:.2f} known, "
              f"{out['review_calls_unknown_cost']} calls with no figure")
    for row in rows[-5:]:
        print(f"  {row['at']}  {row['kind']:<10} {row.get('task', '')} "
              f"{str(row.get('why', ''))[:60]}")
    return 0


def command_doctor(args) -> int:
    space = _space(args)
    book = Backlog(_backlog_of(space))
    print(doctor_text(diagnose(book, space)))
    return 0


def command_report(args) -> int:
    space = _space(args)
    print(as_text(report(space)))
    return 0


def command_stop(args) -> int:
    space = _space(args)
    space.stop()
    if args.now:
        stopped = space.kill_running()
        print(f"stopped now; signalled {stopped or 'nothing'}; worktrees kept")
    else:
        print("stopping after the running tasks finish")
    return 0


def _backlog_of(space: Workspace) -> str:
    """The backlog the campaign was started with, resolved by `campaign_of`
    (lib/campaign_of.py — the one home for this, shared with the dashboard).
    An exit when there is no init event: every caller here needs a real path,
    never the empty string that function uses to say there isn't one yet."""
    path = backlog_of(space)
    if not path:
        raise SystemExit("this workspace has no init event; run `init` first")
    return path
