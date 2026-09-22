"""One slicer call, split from `turn.py` at the 200-line cap.

One stuck CODE card — or, when nothing is startable, the source gap — goes to
the integrated slicer. `plan_phase` is its only caller now: this used to run at
the top of every driver turn, which is the plan phase and the build phase mixed
by construction. `taking` is what a lane is building, and is never the target."""

from __future__ import annotations

import pathlib
import shutil
from collections.abc import Sequence

import clean_tree
import runner
import source_gap
import where
from finishing import declared_sources
from keep_branch import resolve
from slice_outcome import MAX_SLICES, record_outcome


def slice_pending(book, space, taking: Sequence[str] = ()) -> None:
    """One stuck CODE card is handed to the slicer — the integrated standalone
    (SLICER.md step 2), one card per call, called only by the plan phase.

    Only when the task list is the tree the slicer writes; a wall is a card in
    a state the loop will not retry (needs_slice, or refused with its replans
    spent) that no human holds and that is not LIVE. The slicer's own trace,
    prompts and answers land beside the task list; here only the step and the
    outcome are recorded.

    `taking` names cards a caller knows are being built; the claims file names
    what any lane has actually started, and the two together are what a build in
    flight means at THIS moment. A plan phase runs with the driver stopped, so
    both are normally empty — they are read anyway, because a campaign whose
    driver was not stopped must not have a card rewritten under its builder. A
    card in either is never the target: a build in flight can write itself into
    a wall status, and slicing it would rewrite the card under its own builder.

    A startable card does NOT hold the source gap back. It did while this ran at
    the top of a build turn, where building beat planning because both were
    happening; in a plan phase nothing is building, and the first molecule's own
    atoms are startable the moment it is written — so that rule ended the plan
    after one molecule, with every later molecule unwritten (found by the first
    real campaign run on this branch, 2026-09-18)."""
    if not book.is_tree:
        return
    from backlog_decision import broken_wait
    from backlog_status import is_wall
    rows = book.tasks()
    busy = set(taking) | set(space.running())
    target = None
    for row in rows:
        if not is_wall(row) or row.get("id") in busy:
            continue
        broken = broken_wait(row, rows)
        if broken:
            # `is_wall` reads the card's shape, never its needs, so a wall
            # waiting on a missing id was this call's target even though no plan
            # for it could pass.
            # card. The slicer's own law refuses external needs that are not
            # there: handing it over buys three paid rounds and the same
            # answer. Uncharged — no slice round, and the card is not touched.
            space.event("slice_skipped", task=row["id"], why=broken)
            continue
        target = row
        break
    if target is not None and int(target.get("slices") or 0) >= MAX_SLICES:
        # unheld but at the cap: whatever released the hold earns one fresh try, persisted now
        target = book.note(target["id"], slices=None)
    label = target["id"] if target else "the sources"
    sources = declared_sources(space)   # a campaign that declared none is not sliced
    if not sources:
        space.event("slice_skipped", task=label,
                    why="no approved sources are recorded for this campaign")
        return
    if target is None and not source_gap.may_try(space):
        # The gap answered "needs a person" once, or its answered failures hit
        # the cap. Neither waits for a person (astra's section H 5): the stop
        # stands until a source is declared, and a campaign that gets none ends
        # with its gaps named (`source_gap`).
        return
    import sys as _sys
    slicer = pathlib.Path(__file__).resolve().parents[2] / "slicer" / "slicer.py"
    # the slicer reads a CLEAN checkout of the campaign branch tip — the
    # main checkout is a working tree whose edits are nobody's record
    import subprocess
    branch = next((e.get("branch") for e in space.events()
                   if e.get("kind") == "init" and e.get("branch")), "") or where.branch()
    repo = where.repo(space)
    tip = resolve(str(repo), branch)
    if not tip:
        # fail CLOSED: slicing an unrelated HEAD would plan against the wrong code
        space.event("slice_skipped", task=label,
                    why=f"the campaign branch {branch} is not in {repo}")
        return
    with clean_tree.checkout(tip, repo) as (clean, cannot):
        if clean is None:
            space.event("slice_skipped", task=label,
                        why=f"no clean checkout of {where.branch()}: {cannot}")
            return
        argv = [_sys.executable, str(slicer), "--repo", str(clean),
                "--backlog", str(book.path), "--campaign", str(space.root)]
        goal = next((e.get("goal") for e in space.events() if e.get("kind") == "init"), "")
        if goal:
            argv += ["--goal", str(goal)]
        if target is not None:
            argv += ["--target", target["id"]]
            # EVERY recorded finding and gate output is the slicer's evidence —
            # an alphabetical last-two once dropped the round that mattered
            kinds = ("*-contract-answer.txt", "*-diff-review-answer.txt",
                     "*-gate-output.txt", "*-red-first.txt", "*-diff.txt")
            # copied INTO the clean tree: the slicer rightly refuses to read
            # paths outside the checkout it plans against. The whole LINEAGE
            # travels — a wall's ancestors' findings are prior art (SLICER.md)
            inside = clean / ".slicer-evidence"
            inside.mkdir(parents=True, exist_ok=True)
            by_id = {str(r.get("id")): r for r in rows}
            chain, cur = [], target
            while cur and str(cur.get("id")) not in chain:
                chain.append(str(cur.get("id")))
                cur = by_id.get(str(cur.get("sliced_from") or ""))
            for tid in chain:
                calls = pathlib.Path(space.root) / "calls" / tid
                if not calls.is_dir():
                    continue
                for pattern in kinds:
                    for artifact in sorted(calls.glob(pattern)):
                        named = inside / f"{tid}-{artifact.name}"
                        shutil.copy2(artifact, named)
                        argv += ["--evidence", str(named)]
            # the kept worktree holds what the gate actually judged — a gate
            # failure records no diff artifact, so the diff is taken here
            kept = str(target.get("rebuild_from") or target.get("worktree") or "")
            if kept and (pathlib.Path(kept) / ".git").exists():
                body = subprocess.run(["git", "-C", kept, "diff", "HEAD"],
                                      capture_output=True, text=True, check=False).stdout or ""
                others = subprocess.run(["git", "-C", kept, "ls-files", "--others",
                                         "--exclude-standard"],
                                        capture_output=True, text=True, check=False)
                for name in (others.stdout or "").splitlines():
                    try:
                        body += (f"\n--- untracked: {name} ---\n"
                                 + (pathlib.Path(kept) / name).read_text("utf-8")[:20000])
                    except (OSError, UnicodeDecodeError):
                        body += f"\n--- untracked (unreadable): {name} ---\n"
                if body.strip():
                    (inside / "000-worktree-diff.txt").write_text(body)
                    argv += ["--evidence", str(inside / "000-worktree-diff.txt")]
        argv += [arg for src in sources for arg in ("--source", src)]
        with space.step(label, "slice") as note:
            try:
                # above every inner budget: three 900 s planner repairs plus
                # two 1800 s reviews — pre-empting a valid repair round wasted it.
                # Through `runner`, like every other paid child: the slicer's
                # own planner and reviewer calls are in its group, so they end
                # with it, and it dies with the driver that started it.
                done = runner.run(argv, timeout=7200)
            except subprocess.TimeoutExpired:
                done = subprocess.CompletedProcess(
                    argv, 124, stdout="",
                    stderr="timeout: the slicer exceeded its 7200 s ceiling")
            note(rc=done.returncode, said=(done.stdout or done.stderr)[-160:])
    # the checkout and the temp parent that held it are gone with the block
    said = (done.stdout or "") + (done.stderr or "")
    record_outcome(book, space, label, target, said, done.returncode)
