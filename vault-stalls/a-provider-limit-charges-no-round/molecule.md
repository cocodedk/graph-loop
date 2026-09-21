---
source:
- docs/rfc/stalls-brief.md:31
- docs/rfc/stalls-brief.md:32
files:
- graph/lib/loop_judge_retry.py
- graph/lib/loop_steps.py
- graph/tests/test_loop_faults.py
status: todo
gate_reviewed_first: true
expect_red: a provider limit charges the card a round
---

## Goal

A builder call that ends `limit`, `auth` or `capacity` after it had already spent figures charges the card no rebuild round: the card goes back to `todo` in the same worktree with the `rebuild_round` it already had, and the `rebuild_queued` event records the round as not charged. A card at round 2 that meets a limit is still `todo` at round 2, not `rejected`. A call that ended `crash` still charges its round.

## Why

`back_in_place` already has this branch, and it is review-only: `review_kind` is passed by a review call site alone, and its docstring says "never a builder fault". A builder's limit therefore takes the counted path at graph/lib/loop_judge_retry.py:91, and three of them in a row write `the builder's call went wrong (limit) 3 rounds running; a person re-slices` at :99 — the ending two good cards actually got, with nothing wrong with either card.

The unpaid half is already right: graph/lib/loop_steps.py:144 returns `waiting` and spends nothing when the belt walked and the resource provably did nothing. What is missing is the paid half — a limit that cut a call off part way leaves real work in the tree, so the tree is kept and the card continues there, but the wall was the provider's and not the card's.

`resources.refused_before_reading` is the one predicate that names the three kinds, and it is already imported here, so the smallest change is to let the builder's call site say which kind it was and to read the same predicate for it. A `crash`, a `malformed` answer or a denied tool is not in that set and must go on charging, or a card with a genuinely broken build would never stop.

graph/lib/loop_judge_retry.py is 148 lines and graph/lib/loop_steps.py is under the cap; neither needs splitting for this.

graph/tests/test_loop_faults.py pins the charging behaviour under two names — `test_a_limit_hit_part_way_through_keeps_the_paid_work_in_place` and `test_an_unknown_limit_that_edited_the_tree_is_paid_work_kept_in_place`, both asserting `("todo", 1, out.worktree)`. Those two sentences are what this card changes, so the file is in this card's hands and the gate does not run it. `EXPECTED_TESTS` at the top of that file counts its own cases; leave the count right.

## Done when

The gate passes. With the `test_loop` rig: for each of `limit`, `auth` and `capacity`, a build call that returns that kind with `cost=1.2, tokens=500` leaves the card `todo`, `rebuild_round` unset or 0, `rebuild_from` equal to the outcome's worktree, and the last `rebuild_queued` event for the card carrying `charged` exactly `False`. A card starting at `rebuild_round: 2` that meets such a limit is still `("todo", 2)`. A build call that returns `crash` with the same figures leaves `rebuild_round` 1. graph/tests/test_loop.py, graph/tests/test_loop_rebuild.py, graph/tests/test_backlog_rounds.py, graph/tests/test_live_accounts.py and graph/tests/test_keep_combined_owner.py stay green. The gate does not prove anything about cooldowns, about which provider is called next, or about how a limit is classified by `triage_signatures`.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import os, pathlib, sys
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
sys.path.insert(0, str(root / "graph" / "tests"))
try:
    import tmp_root  # noqa: F401 — every temp file of this process under one root
    from providers import Outcome
    from test_loop import Fakes, loop_for, task
except ImportError as gone:
    sys.exit(f"a provider limit charges the card a round: {gone}")

RED = "a provider limit charges the card a round"


def paid(kind):
    """A call that spent figures and then hit the provider's wall."""
    return Fakes(build=[Outcome(kind, text=f"{kind} reached mid-call", cost=1.2, tokens=500),
                        Outcome(kind, text="never called")])


for kind in ("limit", "auth", "capacity"):
    loop, book, space = loop_for(task(), paid(kind))
    out = loop.run_task(book.task("T1"))
    row = book.task("T1")
    assert row["status"] == "todo", f"{RED}: {kind} left the card {row['status']}"
    assert int(row.get("rebuild_round") or 0) == 0, \
        f"{RED}: {kind} charged round {row.get('rebuild_round')}"
    assert row.get("rebuild_from") == out.worktree, \
        f"{RED}: {kind} lost the worktree: {row.get('rebuild_from')!r}"
    queued = [one for one in space.events()
              if one.get("kind") == "rebuild_queued" and one.get("task") == "T1"]
    assert queued and queued[-1].get("charged") is False, \
        f"{RED}: the {kind} round was recorded as charged: {queued}"

# The rebuild state it already had survives, and a limit at round 2 does not
# reject it: that is the ending the campaign actually recorded.
loop, book, _ = loop_for(task(rebuild_round=2), paid("limit"))
loop.run_task(book.task("T1"))
row = book.task("T1")
assert (row["status"], int(row.get("rebuild_round") or 0)) == ("todo", 2), \
    f"{RED}: a limit at round 2 left the card {row['status']} at round {row.get('rebuild_round')}"

# A call that went wrong for its own reasons still spends a round.
loop, book, _ = loop_for(task(),
                         Fakes(build=[Outcome("crash", text="it died", cost=1.2, tokens=500)]))
loop.run_task(book.task("T1"))
row = book.task("T1")
assert int(row.get("rebuild_round") or 0) == 1, \
    f"a crash stopped charging a round: {row.get('rebuild_round')}"
print("PROBE OK")
PY
(cd graph/tests && timeout 600 python3 -m unittest test_loop)
(cd graph/tests && timeout 600 python3 -m unittest test_loop_rebuild)
(cd graph/tests && timeout 600 python3 -m unittest test_backlog_rounds)
(cd graph/tests && timeout 600 python3 -m unittest test_live_accounts)
(cd graph/tests && timeout 600 python3 -m unittest test_keep_combined_owner)
```

## Note

Red today: the probe fails with `a provider limit charges the card a round: limit charged round 1`, because graph/lib/loop_steps.py tells `back_in_place` nothing about the kind and graph/lib/loop_judge_retry.py:82 reads `review_kind` alone. graph/tests/test_loop_faults.py is in the file list because two of its cases state the behaviour this card changes; the gate does not run it, and its `EXPECTED_TESTS` count must stay right. Every code file stays under 200 lines. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the files listed.
