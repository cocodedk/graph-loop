"""One task, start to finish: prove, review, build, gate, review, record.

The order is the whole point, and every step in it was bought with a failure:

  held?        a task a human holds is never started
  lock         a task that touches the live stack takes the lock, or waits
  prove red    a gate that has never failed proves nothing
  review       the contract is read before a builder edits anything
  build        the routed builder at medium (high only after a failed medium
               build of the same contract), work account first, the other on a
               usage limit or a refused session; a live task is called once, except that a refused
               session never reached the model and may try the other account
  names        a card that uses what nothing has made yet is refused, free
  scope        a file outside the task's list refuses the work
  gate         the exit code decides, and the worktree is kept when it fails
  review       the diff is read by a fresh reviewer before anything is kept
  rebuild      a rejected diff goes back to the builder, three rounds in all
  evidence     no files, not live: contract, one gate call (credential-scrubbed;
               boxed when bubblewrap works), done or failed
"""

from __future__ import annotations

import pathlib

import molecule
from backlog import Backlog
from backlog_status import is_live, runs_alone
from keep import Keeper
from loop_evidence import red_first
from loop_judge import REBUILD_ROUNDS, contract, judge
from loop_peers import lost_why, open_why, release_live_peers, restate_live_peers
from loop_scope import gate_files
from loop_start import already_finished
from loop_steps import build
from loop_tree import for_this_round
from loop_types import ACCOUNTS, TaskOutcome
from prompts import already_read, build_prompt, contract_prompt, diff_prompt
from workspace import Workspace
from worktree import LOCK_WAITS, Worktree, stack_lock

__all__ = ["ACCOUNTS", "REBUILD_ROUNDS", "Loop", "TaskOutcome", "build_prompt",
           "contract_prompt", "diff_prompt"]


class Loop:
    """The task runner. `build` and `review` are injected so fakes can stand in."""

    def __init__(self, *, repo: str, backlog: Backlog, space: Workspace,
                 build, review, commit: str = "HEAD", branch: str = ""):
        self.repo = repo
        self.backlog = backlog
        self.space = space
        self.build = build
        self.review = review
        self.commit = commit
        self.lock = stack_lock()   # the STACK's lock, not this campaign's
        # Accepted work is committed on a campaign branch, and the next task
        # starts from that tip — never from a HEAD that predates it.
        self.keeper = Keeper(repo, branch, base=commit, workspace=space.root) if branch else None

    def run_task(self, task: dict) -> TaskOutcome:
        task_id = task["id"]
        # A finished card never opens a worktree or calls a builder or
        # reviewer again: a stale reference to it is not new work.
        outcome = already_finished(task)
        if outcome is not None:
            return outcome
        editable_gate = gate_files(task)
        if editable_gate and not task.get("gate_files_are_the_work"):
            why = ("the builder may edit the test its own gate runs "
                   f"({', '.join(editable_gate)}); either take them out of its hands "
                   "or say that writing them is the work (gate_files_are_the_work)")
            self.space.event("refused", task=task_id, step="scope_of_gate", why=why)
            self.backlog.set_status(task_id, "refused_contract", refused_why=why)
            return TaskOutcome("refused", why)
        if task.get("blocked_by_human"):
            self.space.event("held", task=task_id)
            return TaskOutcome("held", "a human holds this task")

        # The lock is for whatever must run ALONE on the stack: `runs_alone`,
        # not `is_live` — a no-files evidence task is not live but still needs it.
        # Taken INSIDE the try: a failure between taking it and finishing the
        # task must still give it back, or every later live card waits on a
        # ghost. `taken` — not `alone` — says whether THIS call holds it.
        alone = runs_alone(task)
        taken = False
        try:
            if alone:
                if not self.lock.take(task_id):
                    if self.lock.unreadable():
                        return self._lock_unreadable(task)
                    return TaskOutcome("waiting", f"the live stack is held by {self.lock.holder()}")
                taken = True
                if task.get("live_waits"):
                    # the lock read plainly this time: the count of consecutive
                    # doubts restarts, and the reason it wrote goes with it
                    self.backlog.note(task_id, live_waits=None, refused_why=None)

            tree, in_place = for_this_round(self, task)

            out = self._through(task, tree, in_place)
            if is_live(task) and out is not None \
                    and out.state not in ("done", "blocked", "held", "environment"):
                # Whatever went wrong after the call — the gate, the review, an
                # exception — the next turn must not repeat it on a moved stack.
                # Never over `held`: another writer decided this card while the
                # round ran, and the guard returning it preserved that decision.
                why = f"a live call was made and the turn ended {out.state}: {out.why[:200]}"
                self.backlog.set_status(task_id, "live_turn_ended", blocked_by_human=True,
                                        held_by="loop", refused_why=why)
                self.space.alert(task_id, why)
            return out
        except BaseException:
            # The task stays live_call_open and nothing recorded how the call
            # ended: that is the doubt the peers were held for, so it outlives
            # this turn rather than being cleared by the release below.
            if taken:
                restate_live_peers(self.backlog, open_why(task_id), lost_why(task_id))
            raise
        finally:
            if taken:
                try:
                    # Before the lock goes back: after it, the next runner's
                    # own holds exist and a release could free those instead.
                    release_live_peers(self.backlog, open_why(task_id))
                finally:
                    # Given back even when the release above raises: a lock
                    # leaked here is held forever, by nothing.
                    self.lock.give_back()

    def _lock_unreadable(self, task: dict) -> TaskOutcome:
        """The live-stack lock exists and names no holder anyone can check.

        Nobody can be asked whether that holder still lives, so waiting on it
        never ends: this card came back `waiting` every turn and reached no
        actor at all (astra round 4, finding 10). The lock FILE stays — what
        cannot be read cannot be cleared — the failure is recorded every turn,
        and at `LOCK_WAITS` the card carries it as its reason and stops being
        the picker's. Nothing in a build turn can take it from there — what the
        loop parked as nobody's is the plan phase's, which drops it with the gap
        named (`plan_phase.drop_loop_holds`, keyed on `held_by`).
        """
        task_id = task["id"]
        why = f"the live-stack lock {self.lock.path} names no holder that can be checked"
        waits = int(task.get("live_waits") or 0) + 1
        self.space.event("live_lock_unreadable", task=task_id, waits=waits, why=why)
        if waits < LOCK_WAITS:
            self.backlog.note(task_id, live_waits=waits)
        else:
            self.backlog.set_status(task_id, "live_lock_unreadable", held_by="loop",
                                    live_waits=None, refused_why=why)
        return TaskOutcome("waiting", why)

    # ------------------------------------------------------------------ steps

    def _through(self, task: dict, tree: Worktree, in_place: bool = False) -> TaskOutcome:
        task_id = task["id"]
        gate = task.get("gate") or "false"
        rebuild = int(task.get("rebuild_round") or 0)

        # Asked of the WORKTREE, which is what a builder sees. A card naming
        # something nothing makes costs a file read here, a build and two
        # reviews to find out later.
        unknown = molecule.unknown_names(task, self.backlog.tasks(), pathlib.Path(tree.path))
        if unknown:
            self.space.event("refused", task=task_id, step="names", why=unknown)
            self.backlog.set_status(task_id, "refused_contract", refused_why=unknown)
            tree.keep(f"names: {unknown[:200]}")
            return TaskOutcome("refused", unknown, tree.path)

        # `red_first` (lib/loop_evidence.py) decides whether proving the gate
        # red is worth doing at all, and reads a rewritten gate before it runs.
        reviewed_first = bool(task.get("gate_reviewed_first"))
        stopped = red_first(self, task, tree, gate, rebuild, in_place, reviewed_first)
        if stopped is not None:
            return stopped

        if already_read(task, in_place, reviewed_first):
            # Already read: a rebuild round's contract was accepted before round
            # one, and a rewritten gate was reviewed above, before it ran. The
            # digest is what makes that true — a contract edited after its
            # acceptance is one nobody has read, and it goes back to the review.
            self.space.event("skipped_contract", task=task_id,
                             why=(f"rebuild round {rebuild}: accepted before round one"
                                  if in_place else "the rewritten gate was reviewed before it ran"))
        else:
            refused = contract(self, task, tree, in_place)
            if refused is not None:
                return refused

        # No files, no live gate: nothing for a builder to edit, so the builder
        # is skipped. `judge` itself ends this case, right after its one gate
        # call (credential-scrubbed; boxed when bubblewrap works) — before the
        # diff review, since there is no diff to read.
        if is_live(task) or task.get("files"):
            stopped = build(self, task, tree, in_place)
            if stopped is not None:
                return stopped
        return judge(self, task, tree, gate, rebuild)
