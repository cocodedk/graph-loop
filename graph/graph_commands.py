"""The driver's commands other than `run`. The two real providers, routed by
`model_router.choose` (docs/ROUTER.md), live in `real_calls.py`.

`graph-goal.py` keeps `run` and the command line; one-off commands and shared constants live here.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import alert_email
import durable
import where
from backlog import Backlog
from campaign_of import backlog_of
from doctor import as_text as doctor_text
from doctor import diagnose
from keep_branch import campaign_branch
from plan_phase import command_plan  # noqa: F401 — the plan phase's door stays here
from real_calls import _real_build, _real_review  # noqa: F401 — the door stays here
from report import as_text, report
from turn import (  # noqa: F401 — the door stays here
    plan_with_claude,
    replan_pending,
    run_lanes,
    stood_down,
    taking_now,
    turn_opens,
)
from waves import say as say_waves
from workspace import Workspace
from workspace_claims import say
from workspace_repo import initial_root

DEFAULT_WORKSPACE = where.campaign()
# What a builder may run lives in lib/tools.py: a code task gets a shell, a
# live task gets only the helper. BUILDER_TOOLS is the code task's list.
from tools import builder_tools

BUILDER_TOOLS = builder_tools({})


def _space(args) -> Workspace:
    return Workspace(args.workspace or DEFAULT_WORKSPACE)


def command_contact(args) -> int:
    space = _space(args)
    channel = args.channel.strip()
    if not channel:
        raise SystemExit("contact requires an email address")
    alert_email.send("Campaign contact test", "This campaign can now reach its person.",
                     subject="graph-loop: can this campaign reach you?",
                     recipient=channel)
    with space.only_writer():
        durable.replace(space.root / "contact", channel + "\n")
    return 0


def command_init(args) -> int:
    book = Backlog(pathlib.Path(args.backlog).resolve())
    space = _space(args)
    root = (where.repo(space) if any(row.get("kind") == "init" for row in space.events())
            else initial_root())
    branch = campaign_branch(str(root), args.branch or where.branch())
    space.init(goal=args.goal or "the backlog", backlog=str(book.path),
               branch=branch, repo=str(root))
    declare_sources(space, list(getattr(args, "source", None) or []))
    (space.root / "approved").unlink(missing_ok=True)
    # What the campaign RECORDS, never what this call asked for. An init that
    # finds an existing campaign changes nothing, and printing the argument
    # back read as confirmation that it had been recorded.
    kept = Backlog(backlog_of(space))
    say(f"campaign at {space.root}\nbacklog {kept.path} — {len(kept.tasks())} tasks")
    if kept.path != book.path:
        say(f"this campaign already existed: it still points at {kept.path}, "
              f"not at {book.path}")
    say("nothing runs until: graph-goal.py approve")
    return 0


def declare_sources(space, paths: list[str]) -> list[str]:
    """Validated, repo-relative approved sources, recorded on the campaign.
    Shared by `init --source` and the `sources` command, so an existing
    campaign can declare or move its sources without a new init."""
    good = []
    root = where.repo(space)
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
    say(f"approved sources recorded: {', '.join(good) or 'none'}")
    return 0


def command_approve(args) -> int:
    space = _space(args)
    (space.root / "approved").write_text("approved\n", "utf-8")
    space.event("approved")
    say("approved — `run` will now start tasks")
    return 0


def command_answer(args) -> int:
    space = _space(args)
    book = Backlog(_backlog_of(space))
    book.set_status(args.card_id, "refused_contract", refused_why=args.decision,
                    blocked_by_human=None, held_by=None, triage=None,
                    accepted_criteria=None, contract_seen=None)
    space.event("answered", task=args.card_id, decision=args.decision)
    return 0


def command_status(args) -> int:
    from node_status import say as say_nodes
    space = _space(args)
    rows = space.events()
    book = Backlog(_backlog_of(space))
    done = [row for row in book.tasks() if row.get("status") == "done"]
    say(f"campaign {space.root}")
    say(f"  approved: {(space.root / 'approved').exists()}   stopping: {space.stopping()}")
    say(f"  tasks: {len(done)} done of {len(book.tasks())}")
    say_nodes(book.tasks())
    running = space.running()
    say(f"  running: {', '.join(running) or 'nothing'}")
    held = [row['id'] for row in book.waiting_for_human()]
    if held:
        # The hold stays on the card as stored evidence; nothing takes it off
        # but a person, and the campaign ends naming it.
        say(f"  held on the card: {', '.join(held)}")
    ready = [row["id"] for row in book.startable(running=list(running))]
    say(f"  ready now: {', '.join(ready) or 'nothing'}")
    say_waves(book.tasks(), running=list(running))
    out = report(space)
    say(f"  attempts recorded: {sum(1 for r in rows if r.get('kind') == 'attempt')}"
          f"   known spend: ${out['spend_known']:.2f}")
    if out["review_spend_known"] or out["review_calls_unknown_cost"]:
        say(f"  reviews: ${out['review_spend_known']:.2f} known, "
              f"{out['review_calls_unknown_cost']} calls with no figure")
    for row in rows[-5:]:
        say(f"  {row['at']}  {row['kind']:<10} {row.get('task', '')} "
              f"{str(row.get('why', ''))[:60]}")
    return 0


def command_doctor(args) -> int:
    space = _space(args)
    where.repo(space)
    book = Backlog(_backlog_of(space))
    say(doctor_text(diagnose(book, space)))
    return 0


def command_report(args) -> int:
    space = _space(args)
    say(as_text(report(space)))
    return 0


def command_stop(args) -> int:
    space = _space(args)
    space.stop()
    if args.now:
        stopped = space.kill_running()
        say(f"stopped now; signalled {stopped or 'nothing'}; worktrees kept")
    else:
        say("stopping after the running tasks finish")
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
