"""The steps between the red proof and the gate: contract review and build.

Each is a function of the loop, so `loop.py` stays the short story of one task
and this file holds the two conversations with the models.
"""

from __future__ import annotations

import resources
from backlog_status import is_live
from distress import read_result, tail
from effort import build_effort
from loop_judge_retry import moved_first, scope_fault
from loop_peers import hold_live_peers, open_why
from loop_resume import resuming
from loop_steps_live import live_call_lost
from loop_types import TaskOutcome
from prompts import build_prompt
from tools import builder_denies, builder_guard, builder_tools, write_gate_script
from worktree import HeadMoved, Worktree, changed_outside, discard


def _paid(out) -> bool:
    """The call provably spent something — money, tokens, or a tool ran.

    Unknown numbers read UNPAID here: the ordinary weekend limit is the CLI's
    banner with no JSON answer and no figures, and treating it as paid would
    break the belt on the first account and burn a counted round per pick.
    Figures are not the only witness, though — the caller also compares the
    worktree against its pre-call snapshot, so a mid-work death that dropped
    its figures is still caught by the edits it left behind. `unstarted`
    stays the stricter, live-task question."""
    return (out.cost or 0) > 0 or (out.tokens or 0) > 0 or out.denials > 0


def build(loop, task: dict, tree: Worktree, in_place: bool = False) -> TaskOutcome | None:
    """Build in the worktree, read the builder's last line, check its scope.
    None means the work is ready for the gate; otherwise the ending."""
    task_id = task["id"]
    if resuming(loop, task, tree, "gate"):
        # The gate finished in this very tree, on this contract, with this
        # diff: only the review is missing, and a builder call would re-pay
        # work that already stands (finding 22).
        loop.space.event("resumed", task=task_id, phase="gate")
        return None
    prompt = build_prompt(task, in_place)
    loop.space.artifact(task_id, "build-prompt", prompt)
    # A live builder is called ONCE, with one exception. A call that hit a limit or
    # crashed may already have run a helper command, and a second account would
    # repeat a live action with no proof the first did nothing. A refused session is
    # different: the call never reached the model, so no tool ran and there is
    # nothing to repeat. Without that exception one expired account quarantined
    # every live card in the campaign, turn after turn.
    belt = resources.belt("build")
    spent = resources.Exhausted()
    # What the tree held before any call this turn: a refusal whose figures are
    # missing is judged by the edits it left behind, not by inference (B4 r4).
    write_gate_script(task)   # the builder is told the gate is what done means
    fingerprint = tree.diff()
    if not in_place:
        # On the card BEFORE the builder is paid, and only here: a driver that dies
        # mid-build resumes on this tree, and a tree recorded any earlier would
        # let a restart skip red-first with no proof it ever ran.
        loop.backlog.note(task_id, rebuild_from=tree.path)
    if is_live(task):
        # Durable BEFORE the call: a provider exception or a driver death would
        # otherwise leave the task todo and the next turn would repeat the live
        # action. The endings below move it on; nothing else does. Its peers are
        # held with it — an exception releases the stack lock, and another live
        # task would start on a stack this one may already have moved.
        loop.backlog.set_status(task_id, "live_call_open",
                                refused_why="a live call was started and its end is not recorded")
        # On the card this round carries too: every ending compares the two
        # (`contract.moved_under`), and the loop's own move is not a person's.
        task["status"] = "live_call_open"
        hold_live_peers(loop.backlog, task_id, open_why(task_id))
    timed_out = False
    for resource in belt:
        if spent.skip(resource):
            continue           # this account or this model has already said no
        account = resource.account
        with loop.space.step(task_id, "build") as note:
            built = loop.build(prompt, account=account, model=resource.model, cwd=tree.path,
                               files=task.get("files") or [], tools=builder_tools(task, tree.path),
                               denies=builder_denies(task), guard=builder_guard(task),
                               effort=build_effort(task),
                               # a rebuild round continues the SAME work: resume it rather
                               # than pay to read every file again
                               # a session lives in ONE account's configuration: resume it
                               # only under the account that made it
                               resume=(str(task.get("session") or "")
                                       if in_place and task.get("session_account") == account else ""))
            note(account=account, on=str(resource), outcome=built.kind,
                 cost=built.cost, effort=build_effort(task))
        loop.space.artifact(task_id, f"build-answer-{account}",
                            built.raw or built.text)
        loop.space.attempt(task_id, account=account, kind=built.kind,
                           cost=built.cost, tokens=built.tokens,
                           # the outcome's own proof that nothing ran, kept where
                           # a later repair can read it (`triage_effect`)
                           unstarted=built.unstarted)
        if built.session and not built.unstarted:
            # A refusal carries a session id too — an expired one says so by
            # name — and there is nothing in it to resume. Written to the card
            # it reads as "a call ran here" ever after, and every reader
            # believes the card before it believes the log: a live card the
            # loop itself had proved untouched was dropped for it.
            loop.backlog.note(task_id, session=built.session, session_account=account)
        timed_out = timed_out or (built.kind == "crash" and "timeout" in built.text)
        # A builder that committed or switched branches: refused by the hook,
        # not undone here (`lib/hooks/reference-transaction`). This only checks
        # that HEAD is still where the round began — should be unreachable.
        try:
            tree.on_base()
        except HeadMoved as fault:
            return discard(loop, task, tree, fault)
        # One rule for the whole belt: walk on only when the RESOURCE refused
        # before reading and provably did nothing — no figures spent, no edit
        # in the tree. A crash, a malformed answer, or a limit hit part way
        # through (its cost, or the diff it left, says so) means the call did
        # paid work; another resource would spend money repeating it, and the
        # next turn resumes that work. A refused commit never hides that
        # diff: HEAD does not move, so the working tree still differs from it.
        acted = _paid(built) or tree.diff() != fingerprint
        if not resources.refused_before_reading(built.kind) or acted:
            break
        spent.note(resource, built.kind)
        # And a live task walks only when the refusal PROVES it spent nothing —
        # `unstarted` demands the zeroes, not just no proof of spend: a call
        # that reached the model may already have run a helper verb.
        if is_live(task) and not built.unstarted:
            break
    if built.kind != "ok" and is_live(task):
        return live_call_lost(loop, task_id, tree, built, in_place)
    if timed_out and built.kind != "ok":
        # A call ran out of time, not of ideas — whichever account's, and
        # whatever the last account said: the worktree holds an hour of work,
        # so the builder continues there, to the rejected diff's round cap.
        from loop_judge import back_in_place
        return back_in_place(loop, task, tree, "timed_out",
                             "the builder's call ran out of time",
                             "Your previous call ran out of time before it answered. This worktree holds "
                             "what it did: read the diff, continue from it, finish, and say DONE.")
    if resources.refused_before_reading(built.kind) and not acted:
        # No model read the question, no spend on record, and the tree is as it
        # was — a limit, an expired session, capacity: the queue stands and spends
        # no round; a reused worktree holds the rounds before it (at round 0 too,
        # after an uncharged outage); a tree this call cut goes, and the card forgets it.
        if not in_place:
            tree.remove()
            loop.backlog.note(task_id, rebuild_from=None)
        return TaskOutcome("waiting", f"every account refused before reading ({built.kind})",
                           tree.path if in_place else "")
    if built.kind != "ok":
        # Keep partial work here. Crashes, malformed answers and denied tools
        # spend a round; a provider's limit does not.
        from loop_judge import back_in_place
        return back_in_place(loop, task, tree, "harness",
                             f"the builder's call went wrong ({built.kind})",
                             f"Your previous call did not finish ({built.kind}). This worktree holds "
                             "what it did: read the diff, continue from it, finish, and say DONE.",
                             build_kind=built.kind)

    said = read_result(built.text)
    loop.space.event("said", task=task_id, state=said.state, why=said.why[:300])
    if said.state == "UNCLEAR":
        # It did not say plainly what it did. The gate is the judge, so carry
        # on — but a person is told, because a builder that cannot say
        # whether it finished usually did not.
        loop.space.alert(task_id, f"the builder gave no clear answer: {said.why}")
    if said.state in ("BLOCKED", "PARTIAL"):
        # It stopped on purpose and said why: that is the answer, not a failure.
        # The build took an hour, so it passes the same guard every other ending
        # passes first — a drop, a hold or a rewrite decided in that hour is
        # newer than this answer, and parking the card would bring it back.
        with loop.backlog.only_writer():
            ended = moved_first(loop, task, tree, "said")
            if ended is not None:
                return ended
            loop.backlog.set_status(task_id, f"{said.state.lower()}_by_agent",
                                    refused_why=said.why or tail(built.text))
        loop.space.event("needs_a_person", task=task_id,
                         why=said.why or tail(built.text))
        loop.space.alert(task_id, f"the builder stopped: "
                         f"{said.why or tail(built.text)}")
        tree.keep(f"the builder stopped and said why: {said.why[:200]}")
        return TaskOutcome("blocked", said.why or tail(built.text), tree.path)

    outside = changed_outside(tree.path, task.get("files") or [], bool(task.get("may_add_files")))
    if outside:
        why = f"the builder wrote outside its files: {', '.join(outside)}"
        # The gate's own scope fault already goes through this one guard; the
        # builder's now does too, and ends `held` where the card was decided
        # while the build ran, because `failed` is what a lane re-slices.
        moved = scope_fault(loop, task, why)
        tree.keep(moved or why)
        return TaskOutcome("held" if moved else "failed", moved or why, tree.path)
    return None
