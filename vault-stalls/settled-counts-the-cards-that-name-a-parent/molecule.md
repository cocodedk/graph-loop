---
source:
- docs/rfc/stalls-brief.md:66
- docs/rfc/stalls-brief.md:67
files:
- graph/lib/backlog_status.py
status: todo
gate_reviewed_first: true
expect_red: a sliced parent does not count the cards that name it
---

## Goal

`backlog_status.settled` counts a `sliced` card's pieces as the cards that name it in `sliced_from`, as well as the names in its own `Needs`. Over a backlog whose parent `P` is `sliced` with an empty `Needs` and whose two pieces sit in their own folders naming `P`: `P` is not settled while one piece is `todo`, and the card that needs `P` is not ready; `P` is settled once one piece is `done` and the other `dropped`, and only then is that card ready. A `sliced` card whose own `Needs` names a piece the backlog does not hold stays unsettled, and so does a `sliced` card with an empty `Needs` that no card names.

## Why

A tree backlog derives a molecule's `needs` from the atoms in its folder, so a parent sliced by the loop lists its pieces and settles on them. A person cutting a parent by hand writes each piece as its own molecule and names the parent in `sliced_from`; the parent's folder gains no atoms, so `backlog_tree.read` gives it an empty `needs` and `settled` finds no pieces at all. Twelve parents were cut that way in one campaign: seven could never settle and everything behind them waited for ever.

Both sources of pieces must count, and both must be required — a parent that still names a piece in its own `Needs` must keep waiting for it even when every card naming it has finished, or an old `needs` releases a parent early. The empty case stays as it is: a `sliced` card with no pieces from either source is not settled by a rule that is vacuously true, because settling it would release everything behind work nobody wrote. `doctor` is what reports that card; this card does not change the guard that leaves it unsettled.

`sliced_from` is already derived for an atom by `backlog_tree.read` and already read by `doctor.diagnose`, so nothing new has to be written to a card for this. The file is 146 lines today, so the reading fits where `settled` already lives.

## Done when

The gate passes. Over a temporary tree backlog holding `P` (`sliced`, empty `Needs`, no atoms), `P.one` and `P.two` in their own folders with `sliced_from: P`, and `D` (`todo`, `needs: [P]`): with `P.one` `todo` and `P.two` `done`, `settled` leaves out `P` and `D` is not in `Backlog.ready()`; with `P.one` `done` and `P.two` `dropped`, `settled` holds `P` and `D` is in `Backlog.ready()`. A `sliced` parent whose own `Needs` names `ghost`, which the backlog does not hold, is not settled although the one card naming it is `done`. A `sliced` card with an empty `Needs` that no card names is not settled. A list holding a `sliced` row with no `id` and a `done` row naming `P` in `sliced_from` answers exactly `{"P.one"}` rather than raising. graph/tests/test_backlog_settled.py, graph/tests/test_backlog_tree.py, graph/tests/test_waves.py and graph/tests/test_broken_waits_do_not_hide_forever.py stay green. The gate does not prove anything about `doctor`, about `frontier.startable`, or about how a piece is written.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import os, pathlib, sys, tempfile
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
try:
    from backlog import Backlog
    from backlog_status import settled
except ImportError as gone:
    sys.exit(f"a sliced parent does not count the cards that name it: {gone}")

RED = "a sliced parent does not count the cards that name it"


def note(folder, **front):
    folder.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, value in front.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines += [f"- {one}" for one in value]
        else:
            lines.append(f"{key}: {value}")
    lines += ["---", "", "## Goal", "", f"card {folder.name}", ""]
    (folder / "molecule.md").write_text("\n".join(lines), "utf-8")


def cut_by_hand(one, two):
    """A parent cut into pieces that live in their own folders, the way a person
    cuts one: the parent's own Needs is empty and each piece names it."""
    where = pathlib.Path(tempfile.mkdtemp())
    note(where / "P", status="sliced", gate="true")
    note(where / "P.one", status=one, sliced_from="P", gate="true", files=["one.py"])
    note(where / "P.two", status=two, sliced_from="P", gate="true", files=["two.py"])
    note(where / "D", status="todo", needs=["P"], gate="true", files=["d.py"])
    return Backlog(where)


book = cut_by_hand("todo", "done")
rows = book.tasks()
assert "P" not in settled(rows), f"{RED}: P settled while P.one is todo"
assert "D" not in [row["id"] for row in book.ready()], \
    f"{RED}: D is ready while P.one is todo"

book = cut_by_hand("done", "dropped")
rows = book.tasks()
assert "P" in settled(rows), \
    f"{RED}: {sorted(settled(rows))} leaves out P although P.one is done and P.two dropped"
assert "D" in [row["id"] for row in book.ready()], \
    f"{RED}: D is not ready although both pieces of P are finished"

# Its own Needs still counts: a piece the backlog does not hold, named the old
# way, keeps the parent open even when every card naming it has finished.
where = pathlib.Path(tempfile.mkdtemp())
note(where / "P", status="sliced", needs=["ghost"], gate="true")
note(where / "P.one", status="done", sliced_from="P", gate="true", files=["one.py"])
rows = Backlog(where).tasks()
assert "P" not in settled(rows), f"{RED}: P settled although its own Needs names ghost"

# No pieces from either source: settling it would release everything behind it
# on work nobody wrote. `doctor` is what reports such a card.
where = pathlib.Path(tempfile.mkdtemp())
note(where / "P", status="sliced", gate="true")
note(where / "Q", status="done", gate="true", files=["q.py"])
rows = Backlog(where).tasks()
assert "P" not in settled(rows), \
    f"{RED}: P settled although no card names it and it needs nothing"

# A hand-edited flat backlog can hold a sliced row with no id at all, and the
# doctor reads every card through this: it must not stop here.
assert settled([{"status": "sliced", "needs": []},
                {"id": "P.one", "status": "done", "sliced_from": "P"}]) == {"P.one"}, \
    f"{RED}: a sliced row without an id stops settled"
print("PROBE OK")
PY
(cd graph/tests && timeout 600 python3 -m unittest test_backlog_settled)
(cd graph/tests && timeout 600 python3 -m unittest test_backlog_tree)
(cd graph/tests && timeout 600 python3 -m unittest test_waves)
(cd graph/tests && timeout 600 python3 -m unittest test_broken_waits_do_not_hide_forever)
```

## Note

Red today: the probe fails with `a sliced parent does not count the cards that name it: ['P.one', 'P.two'] leaves out P although P.one is done and P.two dropped`, because graph/lib/backlog_status.py:88 reads a parent's pieces from `row.get("needs")` alone. Every code file stays under 200 lines. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the files listed.
