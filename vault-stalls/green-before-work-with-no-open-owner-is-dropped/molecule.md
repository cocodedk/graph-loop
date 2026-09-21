---
source:
- docs/rfc/stalls-brief.md:53
- docs/rfc/stalls-brief.md:54
files:
- graph/lib/loop_evidence.py
status: todo
gate_reviewed_first: true
expect_red: a card another card already delivered is left for a person
---

## Goal

A card whose gate is already green before any work ends `dropped`, with a reason naming the settled card whose files it shares, when no other unsettled card lists those files — and a `dropped` event carrying that reason is written for it. While another unsettled card does list them, and when no settled card shares any of them, the card ends `green_already` as it does today.

## Why

Three code cards ended `green_already` in one campaign because another card had already delivered their work. `green_already` means "a person decides", and every one of those decisions was the same: the work is there, the card is spent. When some settled card already reaches the same files and no open card does, there is nothing left for a builder to do and nobody to wait for, so the loop can say so itself.

Both halves of the condition are needed. Without a settled card that reaches the files there is nobody to name, and the gate may be green for a reason nobody has looked at — which is the case graph/tests/test_loop.py already pins, and it must keep ending `green_already`. Without the "no open card" half, the loop would drop a card while another card is still being built against the same files, and the two are not the same work.

`backlog_reach.reach` and `backlog_reach.overlap` are the repository's only file-overlap primitives, and `backlog_status.settled` is the one answer for what counts as finished; composing them is the whole reading, so nothing new has to be recorded on a card. The drop must write the `dropped` EVENT as well as the status — `doctor_spend` and `source_ended` read that event, and a drop with no `why` is a complaint in the doctor's own check.

graph/lib/loop_evidence.py is 83 lines, so the reading fits beside the branch that writes the status at :78.

## Done when

The gate passes. With the `test_loop` rig, over a card `T1` whose gate is `true` and whose files are `["a.py"]`: with a `done` card `T0` that also lists `a.py` and no other card, `T1` ends `dropped`, its `refused_why` names `T0`, and the campaign holds a `dropped` event for `T1` whose `why` names `T0`. With `T0` and a second `todo` card `T2` that also lists `a.py`, `T1` ends `green_already`. With neither, and with only a `done` card `T3` that lists `b.py` alone, `T1` ends `green_already`. graph/tests/test_loop.py, graph/tests/test_loop_evidence.py, graph/tests/test_red_first_card_moved.py and graph/tests/test_loop_rebuild_gate_green.py stay green. The gate does not prove the wording of the reason beyond the card's id, and it does not prove what the task outcome's state is.

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
    from test_loop import Fakes, loop_for, task
except ImportError as gone:
    sys.exit(f"a card another card already delivered is left for a person: {gone}")

RED = "a card another card already delivered is left for a person"

DELIVERED = {"id": "T0", "goal": "a.py says one", "status": "done", "needs": [],
             "files": ["a.py"], "gate": "grep -q one a.py", "done_when": "a.py says one",
             "kept_at": "2026-08-30T10:00:00Z"}
STILL_OPEN = {"id": "T2", "goal": "a.py says three", "status": "todo", "needs": [],
              "files": ["a.py"], "gate": "grep -q three a.py", "done_when": "a.py says three"}
ELSEWHERE = {"id": "T3", "goal": "b.py says one", "status": "done", "needs": [],
             "files": ["b.py"], "gate": "grep -q one b.py", "done_when": "b.py says one",
             "kept_at": "2026-08-30T10:00:00Z"}


def green_first(extra):
    """T1's gate passes before anything is built against it."""
    loop, book, space = loop_for(task(gate="true"), Fakes(), extra)
    loop.run_task(book.task("T1"))
    return book.task("T1"), space


mine, space = green_first([DELIVERED])
assert mine["status"] == "dropped", \
    f"{RED}: T0 delivered it and the card is {mine['status']}"
assert "T0" in str(mine.get("refused_why") or ""), \
    f"{RED}: the reason does not name the card that delivered it: {mine.get('refused_why')!r}"
dropped = [one for one in space.events()
           if one.get("kind") == "dropped" and one.get("task") == "T1"]
assert dropped and "T0" in str(dropped[-1].get("why") or ""), \
    f"{RED}: no dropped event names the card that delivered it: {dropped}"

# Another card is still being built against those files: not the same work.
mine, _ = green_first([DELIVERED, STILL_OPEN])
assert mine["status"] == "green_already", \
    f"a card an open card still reaches was dropped: {mine['status']}"

# Nobody delivered it: green for a reason nobody has looked at.
mine, _ = green_first([])
assert mine["status"] == "green_already", \
    f"a card nothing delivered was dropped: {mine['status']}"

# A settled card that shares none of its files delivered nothing of its work.
mine, _ = green_first([ELSEWHERE])
assert mine["status"] == "green_already", \
    f"a card was dropped for a settled card sharing none of its files: {mine['status']}"
print("PROBE OK")
PY
(cd graph/tests && timeout 600 python3 -m unittest test_loop)
(cd graph/tests && timeout 600 python3 -m unittest test_loop_evidence)
(cd graph/tests && timeout 600 python3 -m unittest test_red_first_card_moved)
(cd graph/tests && timeout 600 python3 -m unittest test_loop_rebuild_gate_green)
```

## Note

Red today: the probe fails with `a card another card already delivered is left for a person: T0 delivered it and the card is green_already`, because graph/lib/loop_evidence.py:78 writes `green_already` for every green gate and reads nothing about who else lists the files. Every code file stays under 200 lines. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the files listed.
