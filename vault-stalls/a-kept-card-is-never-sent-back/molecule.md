---
source:
- docs/rfc/stalls-brief.md:49
- docs/rfc/stalls-brief.md:50
files:
- graph/lib/loop_judge_gates.py
status: todo
gate_reviewed_first: true
expect_red: a finished card was sent back for its own gate
---

## Goal

When the combined gate fails on a gate owned by another card that is `done` and whose `commit` is an ancestor of the campaign branch, that owner is left alone: it stays `done`, keeps its `commit` and `kept_at`, and is not marked `gate_reviewed_first`. The card that met the failure pays no rebuild round and keeps its worktree, as it does today; the failure is still recorded as a `failed` event with `step` `combined_gate` naming the owner; and that card does not gain the owner in its `needs` and is not offered again as `todo`. An owner that is `done` with no commit on the branch is still sent back for the repair, exactly as today.

## Why

`_send_to_its_owner` writes a `done` owner back to `todo` at graph/lib/loop_judge_gates.py:107. It was written for a gate nobody had kept work behind; against a kept judge it undoes a finished card, and the card that ran into it waits on an owner that is already settled, so the picker offers it straight back into the same ending. Two kept judges went that way in one night, and this morning a kept judge's red gate re-opened a finished card and quarantined the innocent one after two identical endings.

The discriminator is the kept commit, not the status: `graph/lib/keep_pending.py:53-65` already asks `git merge-base --is-ancestor` and reads it the way this repository insists it be read — exit 0 is yes, exit 1 is no, anything else is an error and never a verdict. There is no shared `is_ancestor` helper; either reuse that call the same way or give it one home. `loop.repo` names the repository and `loop.keeper` the campaign branch — ask `Keeper.tip()` rather than the branch name, because a campaign that has kept nothing yet has no branch to resolve and git answers neither yes nor no about a ref that is not there.

A `done` card can carry `commit: None` — `loop_judge.py:86` writes exactly that for an evidence card with no files — so "kept on the branch" must mean a real commit that git says is an ancestor, and a card without one keeps today's behaviour. That is also what keeps graph/tests/test_keep_combined_owner.py green: its `BROKEN` owner is `done` with no commit.

Leaving the candidate card `todo` is the spin this card stops: with the owner settled, a `needs` on it is no wait at all, and the picker hands the card straight back. It needs an ending the picker does not offer — the loop already has that vocabulary in `view_sections.NEEDS_A_PERSON`, and `loop_steps` writes one of them with a `needs_a_person` event beside it. What this card does NOT settle is the judge's own obligation once its code has landed; the loop cannot derive a red-first gate's green form from anything a card carries today, so that stays a person's until it can.

graph/lib/loop_judge_gates.py is 116 lines, so the guard fits without a split.

## Done when

The gate passes. With the `test_loop` rig and a `Loop` on branch `campaign/test`: over a backlog whose owner `T9` is `done` with a gate that is red on the branch tip by itself and with `commit` set to the repository's `HEAD` — an ancestor of the campaign branch — running the candidate card leaves `T9` `done`, with the same `commit` and `kept_at` it had and no `gate_reviewed_first`; the candidate card's `rebuild_round` is unset or 0, its `rebuild_from` is the outcome's worktree, its `needs` does not hold `T9`, its status is not `todo`, and it is not in `Backlog.startable()`; and one `failed` event with `step` `combined_gate` carries `gate_owner` `T9`. Over the same backlog with `T9` carrying no commit, and again with `T9` carrying a parentless commit that the campaign branch does not hold, `T9` is `todo` with `gate_reviewed_first` set, as today. graph/tests/test_keep_combined_owner.py, graph/tests/test_combined_failure_baseline.py, graph/tests/test_keep_combined.py and graph/tests/test_branch_gates_by_files.py stay green. The gate does not prove which ending the candidate card takes, nor anything about re-running the owner's gate later.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import os, pathlib, subprocess, sys
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
sys.path.insert(0, str(root / "graph" / "tests"))
try:
    import tmp_root  # noqa: F401 — every temp file of this process under one root
    from loop import Loop
    from test_loop import Fakes, repo_with, task
except ImportError as gone:
    sys.exit(f"a finished card was sent back for its own gate: {gone}")

RED = "a finished card was sent back for its own gate"

# Red on the branch tip by itself, with or without the candidate's diff: the
# gate is what needs repairing, and no builder of another card can do it.
BROKEN = {"id": "T9", "goal": "a file that is not there", "status": "done", "needs": [],
          "files": ["a.py"], "gate": "test -f never-here", "done_when": "the file is there",
          "kept_at": "2026-08-30T10:00:00Z"}


def run(owner):
    fakes = Fakes()
    where, book, space = repo_with(task(), [dict(owner)])
    head = subprocess.run(("git", "-C", where, "rev-parse", "HEAD"),
                          capture_output=True, text=True, check=True).stdout.strip()
    if owner.get("commit") == "HEAD":
        book.note("T9", commit=head)
    elif owner.get("commit") == "STRAY":
        # A commit git can read that no branch holds: parentless, so it is an
        # ancestor of nothing.
        book.note("T9", commit=subprocess.run(
            ("git", "-C", where, "commit-tree", "HEAD^{tree}", "-m", "stray"),
            capture_output=True, text=True, check=True).stdout.strip())
    loop = Loop(repo=where, backlog=book, space=space, build=fakes.builder,
                review=fakes.reviewer, branch="campaign/test")
    out = loop.run_task(book.task("T1"))
    return book, space, out, head


book, space, out, head = run({**BROKEN, "commit": "HEAD"})
owner = book.task("T9")
assert owner["status"] == "done", \
    f"{RED}: the owner kept at {head[:8]} is {owner['status']}"
assert owner.get("commit") == head, f"{RED}: its commit is {owner.get('commit')!r}"
assert owner.get("kept_at") == BROKEN["kept_at"], \
    f"{RED}: its kept_at is {owner.get('kept_at')!r}"
assert not owner.get("gate_reviewed_first"), \
    f"{RED}: its contract was queued for reading again: {owner.get('gate_reviewed_first')!r}"

mine = book.task("T1")
assert int(mine.get("rebuild_round") or 0) == 0, \
    f"the innocent card was charged round {mine.get('rebuild_round')}"
assert mine.get("rebuild_from") == out.worktree, \
    f"the innocent card lost its worktree: {mine.get('rebuild_from')!r}"
assert "T9" not in (mine.get("needs") or []), \
    f"the innocent card waits on a card that is already settled: {mine.get('needs')}"
assert mine["status"] != "todo", \
    "the innocent card is todo again, so the picker offers it into the same ending"
assert "T1" not in [row["id"] for row in book.startable()], \
    "the innocent card is startable again, so the picker offers it into the same ending"
clash = [one for one in space.events()
         if one.get("kind") == "failed" and one.get("step") == "combined_gate"]
assert [one.get("gate_owner") for one in clash] == ["T9"], \
    f"the failure no longer names the gate's owner: {clash}"

# A done card with no commit at all is not kept work: today's repair stands.
book, _, _, _ = run(BROKEN)
owner = book.task("T9")
assert owner["status"] == "todo" and owner.get("gate_reviewed_first"), \
    f"an owner with no kept commit stopped being sent back: {owner['status']}"

# And neither is a commit the campaign branch does not hold: having a commit is
# not the question, git's answer about it is.
book, _, _, _ = run({**BROKEN, "commit": "STRAY"})
owner = book.task("T9")
assert owner["status"] == "todo" and owner.get("gate_reviewed_first"), \
    f"an owner whose commit is on no branch stopped being sent back: {owner['status']}"
print("PROBE OK")
PY
(cd graph/tests && timeout 600 python3 -m unittest test_keep_combined_owner)
(cd graph/tests && timeout 600 python3 -m unittest test_combined_failure_baseline)
(cd graph/tests && timeout 600 python3 -m unittest test_keep_combined)
(cd graph/tests && timeout 600 python3 -m unittest test_branch_gates_by_files)
```

## Note

Red today: the probe fails with `a finished card was sent back for its own gate: the owner kept at <sha> is todo`, because graph/lib/loop_judge_gates.py:103 asks only whether the owner is `done`. Every code file stays under 200 lines. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the files listed.
