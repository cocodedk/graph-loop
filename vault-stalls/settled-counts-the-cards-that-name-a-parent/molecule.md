---
source:
- docs/rfc/stalls-brief.md:66
- docs/rfc/stalls-brief.md:67
files:
- graph/lib/backlog_status.py
status: done
expect_red: a sliced parent does not count the cards that name it
requirement:
  goal: '`backlog_status.settled` counts a `sliced` card''s pieces as the cards that name it in `sliced_from`,
    as well as the names in its own `Needs`. Over a backlog whose parent `P` is `sliced` with an empty
    `Needs` and whose two pieces sit in their own folders naming `P`: `P` is not settled while one piece
    is `todo`, and the card that needs `P` is not ready; `P` is settled once one piece is `done` and the
    other `dropped`, and only then is that card ready. A `sliced` card whose own `Needs` names a piece
    the backlog does not hold stays unsettled, and so does a `sliced` card with an empty `Needs` that
    no card names.'
  done_when: 'The gate passes. Over a temporary tree backlog holding `P` (`sliced`, empty `Needs`, no
    atoms), `P.one` and `P.two` in their own folders with `sliced_from: P`, and `D` (`todo`, `needs: [P]`):
    with `P.one` `todo` and `P.two` `done`, `settled` leaves out `P` and `D` is not in `Backlog.ready()`;
    with `P.one` `done` and `P.two` `dropped`, `settled` holds `P` and `D` is in `Backlog.ready()`. A
    `sliced` parent whose own `Needs` names `ghost`, which the backlog does not hold, is not settled although
    the one card naming it is `done`. A `sliced` card with an empty `Needs` that no card names is not
    settled. A list holding a `sliced` row with no `id` and a `done` row naming `P` in `sliced_from` answers
    exactly `{"P.one"}` rather than raising. graph/tests/test_backlog_settled.py, graph/tests/test_backlog_tree.py,
    graph/tests/test_waves.py and graph/tests/test_broken_waits_do_not_hide_forever.py stay green. The
    gate does not prove anything about `doctor`, about `frontier.startable`, or about how a piece is written.'
  sources:
  - docs/rfc/stalls-brief.md:66
  - docs/rfc/stalls-brief.md:67
replans: 1
replan_history:
- The gate can pass with an incorrect fallback that uses sliced_from only when Needs is empty. Add a case
  where P needs an existing done card but another card naming P in sliced_from is todo; assert P remains
  unsettled and D remains unready. The frozen requirement requires both sources together, and no recorded
  decision narrows it.
contract_seen: 805e8e026636f351
accepted_criteria:
  goal: '`backlog_status.settled` counts a `sliced` card''s pieces as the union of the names in its own
    `Needs` and the cards that name it in `sliced_from`, and the card settles only when every one of those
    pieces is finished. Over a backlog whose parent `P` is `sliced` and whose two pieces sit in their
    own folders naming `P`, `P` is not settled while one piece is `todo` and is settled once one is `done`
    and the other `dropped`. A card that needs `P` is ready only then. Neither source may stand in for
    the other. A piece named only in `Needs` that is unfinished, or named only in `sliced_from` and unfinished,
    keeps `P` open. A `sliced` card that names a piece the backlog does not hold, or that has no pieces
    from either source, stays unsettled.'
  gate: "set -e -o pipefail\ntimeout 600 python3 - <<'PY'\nimport os, pathlib, sys, tempfile\nroot = pathlib.Path(os.getcwd()).resolve()\n\
    sys.path.insert(0, str(root / \"graph\" / \"lib\"))\ntry:\n    from backlog import Backlog\n    from\
    \ backlog_status import settled\nexcept ImportError as gone:\n    sys.exit(f\"a sliced parent does\
    \ not count the cards that name it: {gone}\")\n\nRED = \"a sliced parent does not count the cards\
    \ that name it\"\n\n\ndef note(folder, **front):\n    folder.mkdir(parents=True, exist_ok=True)\n\
    \    lines = [\"---\"]\n    for key, value in front.items():\n        if isinstance(value, list):\n\
    \            lines.append(f\"{key}:\")\n            lines += [f\"- {one}\" for one in value]\n   \
    \     else:\n            lines.append(f\"{key}: {value}\")\n    lines += [\"---\", \"\", \"## Goal\"\
    , \"\", f\"card {folder.name}\", \"\"]\n    (folder / \"molecule.md\").write_text(\"\\n\".join(lines),\
    \ \"utf-8\")\n\n\ndef cut_by_hand(one, two):\n    \"\"\"A parent cut into pieces that live in their\
    \ own folders, the way a person\n    cuts one: the parent's own Needs is empty and each piece names\
    \ it.\"\"\"\n    where = pathlib.Path(tempfile.mkdtemp())\n    note(where / \"P\", status=\"sliced\"\
    , gate=\"true\")\n    note(where / \"P.one\", status=one, sliced_from=\"P\", gate=\"true\", files=[\"\
    one.py\"])\n    note(where / \"P.two\", status=two, sliced_from=\"P\", gate=\"true\", files=[\"two.py\"\
    ])\n    note(where / \"D\", status=\"todo\", needs=[\"P\"], gate=\"true\", files=[\"d.py\"])\n   \
    \ return Backlog(where)\n\n\ndef both_sources(a_status, piece_status):\n    \"\"\"P names card A in\
    \ its own Needs and is also named by P.one in sliced_from.\"\"\"\n    where = pathlib.Path(tempfile.mkdtemp())\n\
    \    note(where / \"A\", status=a_status, gate=\"true\", files=[\"a.py\"])\n    note(where / \"P\"\
    , status=\"sliced\", needs=[\"A\"], gate=\"true\")\n    note(where / \"P.one\", status=piece_status,\
    \ sliced_from=\"P\", gate=\"true\", files=[\"one.py\"])\n    note(where / \"D\", status=\"todo\",\
    \ needs=[\"P\"], gate=\"true\", files=[\"d.py\"])\n    return Backlog(where)\n\n\ndef ready_ids(book):\n\
    \    return [row[\"id\"] for row in book.ready()]\n\n\nbook = cut_by_hand(\"todo\", \"done\")\nrows\
    \ = book.tasks()\nassert \"P\" not in settled(rows), f\"{RED}: P settled while P.one is todo\"\nassert\
    \ \"D\" not in ready_ids(book), f\"{RED}: D is ready while P.one is todo\"\n\nbook = cut_by_hand(\"\
    done\", \"dropped\")\nrows = book.tasks()\nassert \"P\" in settled(rows), \\\n    f\"{RED}: {sorted(settled(rows))}\
    \ leaves out P although P.one is done and P.two dropped\"\nassert \"D\" in ready_ids(book), \\\n \
    \   f\"{RED}: D is not ready although both pieces of P are finished\"\n\n# Both sources count together.\
    \ Its own Needs is finished, a card naming it is\n# not: a fallback that reads sliced_from only when\
    \ Needs is empty settles P here.\nbook = both_sources(\"done\", \"todo\")\nrows = book.tasks()\nassert\
    \ \"P\" not in settled(rows), \\\n    f\"{RED}: P settled while P.one is todo, because its own Needs\
    \ is done\"\nassert \"D\" not in ready_ids(book), f\"{RED}: D is ready while P.one is todo\"\n\n#\
    \ The other way round: a card naming it is finished, its own Needs is not.\nbook = both_sources(\"\
    todo\", \"done\")\nrows = book.tasks()\nassert \"P\" not in settled(rows), \\\n    f\"{RED}: P settled\
    \ while the card in its own Needs is todo\"\nassert \"D\" not in ready_ids(book), f\"{RED}: D is ready\
    \ while A is todo\"\n\n# Both finished: settled, and only then is D ready.\nbook = both_sources(\"\
    done\", \"done\")\nrows = book.tasks()\nassert \"P\" in settled(rows), f\"{RED}: P not settled although\
    \ both sources are done\"\nassert \"D\" in ready_ids(book), f\"{RED}: D is not ready although both\
    \ sources are done\"\n\n# Its own Needs still counts: a piece the backlog does not hold, named the\
    \ old\n# way, keeps the parent open even when every card naming it has finished.\nwhere = pathlib.Path(tempfile.mkdtemp())\n\
    note(where / \"P\", status=\"sliced\", needs=[\"ghost\"], gate=\"true\")\nnote(where / \"P.one\",\
    \ status=\"done\", sliced_from=\"P\", gate=\"true\", files=[\"one.py\"])\nrows = Backlog(where).tasks()\n\
    assert \"P\" not in settled(rows), f\"{RED}: P settled although its own Needs names ghost\"\n\n# No\
    \ pieces from either source: settling it would release everything behind it\n# on work nobody wrote.\
    \ `doctor` is what reports such a card.\nwhere = pathlib.Path(tempfile.mkdtemp())\nnote(where / \"\
    P\", status=\"sliced\", gate=\"true\")\nnote(where / \"Q\", status=\"done\", gate=\"true\", files=[\"\
    q.py\"])\nrows = Backlog(where).tasks()\nassert \"P\" not in settled(rows), \\\n    f\"{RED}: P settled\
    \ although no card names it and it needs nothing\"\n\n# A hand-edited flat backlog can hold a sliced\
    \ row with no id at all, and the\n# doctor reads every card through this: it must not stop here.\n\
    assert settled([{\"status\": \"sliced\", \"needs\": []},\n                {\"id\": \"P.one\", \"status\"\
    : \"done\", \"sliced_from\": \"P\"}]) == {\"P.one\"}, \\\n    f\"{RED}: a sliced row without an id\
    \ stops settled\"\nprint(\"PROBE OK\")\nPY\n(cd graph/tests && timeout 600 python3 -m unittest test_backlog_settled)\n\
    (cd graph/tests && timeout 600 python3 -m unittest test_backlog_tree)\n(cd graph/tests && timeout\
    \ 600 python3 -m unittest test_waves)\n(cd graph/tests && timeout 600 python3 -m unittest test_broken_waits_do_not_hide_forever)\n"
  done_when: 'The gate passes. Over a temporary tree backlog holding `P` (`sliced`, empty `Needs`), `P.one`
    and `P.two` in their own folders with `sliced_from: P`, and `D` (`todo`, `needs: [P]`): with `P.one`
    `todo` and `P.two` `done`, `settled` leaves out `P` and `D` is not in `Backlog.ready()`; with `P.one`
    `done` and `P.two` `dropped`, `settled` holds `P` and `D` is in `Backlog.ready()`. When `P` has its
    own `Needs` naming an existing `done` card `A` and one card naming `P` in `sliced_from` is `todo`,
    `P` is not settled and `D` is not ready. When `P`''s own `Needs` names a `todo` card and the card
    naming `P` in `sliced_from` is `done`, `P` is not settled. When both sources are finished, `P` is
    settled and `D` is ready. A `sliced` parent whose own `Needs` names `ghost`, which the backlog does
    not hold, is not settled although the one card naming it is `done`. A `sliced` card with an empty
    `Needs` that no card names is not settled. A list holding a `sliced` row with no `id` and a `done`
    row naming `P` in `sliced_from` answers exactly `{"P.one"}` rather than raising. graph/tests/test_backlog_settled.py,
    graph/tests/test_backlog_tree.py, graph/tests/test_waves.py and graph/tests/test_broken_waits_do_not_hide_forever.py
    stay green. The gate proves that `settled` and `Backlog.ready()` use both sources together and that
    each one alone can keep a parent open. It fails on today''s tree, where the `sliced_from` pieces are
    ignored. It does not prove anything about `doctor`, about `frontier.startable`, or about how a piece
    is written.'
  files:
  - graph/lib/backlog_status.py
rebuild_from: /var/tmp/graph-trees/graph-coyz9ff7/task-settled-counts-the-cards-that-name-a-parent
session: 2a79697d-8af5-4a98-9ab0-7e65167ce245
session_account: personal
rebuild_round: 1
rejections:
- 'Diff line 19 (goal): The self-parent exclusion omits a card from the required union and can settle
  it while a piece remains unfinished. — For rows [{"id":"P","status":"sliced","needs":["A"],"sliced_from":"P"},{"id":"A","status":"done"}],
  this condition excludes P from its own pieces, allowing P to settle through A alone. The contract includes
  every card naming P in sliced_from, without a self-reference exception; that union contains unfinished
  P, so P must remain unsettled.'

commit: 6bd623d4ee2a8b1d7d9b2f4c2665fb7d25c749b2
worktree: /var/tmp/graph-trees/graph-coyz9ff7/task-settled-counts-the-cards-that-name-a-parent
kept_at: '2026-09-21T06:41:17Z'
---

## Goal

`backlog_status.settled` counts a `sliced` card's pieces as the union of the names in its own `Needs` and the cards that name it in `sliced_from`, and the card settles only when every one of those pieces is finished. Over a backlog whose parent `P` is `sliced` and whose two pieces sit in their own folders naming `P`, `P` is not settled while one piece is `todo` and is settled once one is `done` and the other `dropped`. A card that needs `P` is ready only then. Neither source may stand in for the other. A piece named only in `Needs` that is unfinished, or named only in `sliced_from` and unfinished, keeps `P` open. A `sliced` card that names a piece the backlog does not hold, or that has no pieces from either source, stays unsettled.

## Why

A tree backlog derives a molecule's `needs` from the atoms in its folder, so a parent sliced by the loop lists its pieces and settles on them. A person cutting a parent by hand writes each piece as its own molecule and names the parent in `sliced_from`; the parent's folder gains no atoms, so `backlog_tree.read` gives it an empty `needs` and `settled` finds no pieces at all. Twelve parents were cut that way in one campaign: seven could never settle and everything behind them waited for ever.

Both sources of pieces must count, and both must be required — a parent that still names a piece in its own `Needs` must keep waiting for it even when every card naming it has finished, or an old `needs` releases a parent early. The empty case stays as it is: a `sliced` card with no pieces from either source is not settled by a rule that is vacuously true, because settling it would release everything behind work nobody wrote. `doctor` is what reports that card; this card does not change the guard that leaves it unsettled.

`sliced_from` is already derived for an atom by `backlog_tree.read` and already read by `doctor.diagnose`, so nothing new has to be written to a card for this. The file is 146 lines today, so the reading fits where `settled` already lives.

## Done when

The gate passes. Over a temporary tree backlog holding `P` (`sliced`, empty `Needs`), `P.one` and `P.two` in their own folders with `sliced_from: P`, and `D` (`todo`, `needs: [P]`): with `P.one` `todo` and `P.two` `done`, `settled` leaves out `P` and `D` is not in `Backlog.ready()`; with `P.one` `done` and `P.two` `dropped`, `settled` holds `P` and `D` is in `Backlog.ready()`. When `P` has its own `Needs` naming an existing `done` card `A` and one card naming `P` in `sliced_from` is `todo`, `P` is not settled and `D` is not ready. When `P`'s own `Needs` names a `todo` card and the card naming `P` in `sliced_from` is `done`, `P` is not settled. When both sources are finished, `P` is settled and `D` is ready. A `sliced` parent whose own `Needs` names `ghost`, which the backlog does not hold, is not settled although the one card naming it is `done`. A `sliced` card with an empty `Needs` that no card names is not settled. A list holding a `sliced` row with no `id` and a `done` row naming `P` in `sliced_from` answers exactly `{"P.one"}` rather than raising. graph/tests/test_backlog_settled.py, graph/tests/test_backlog_tree.py, graph/tests/test_waves.py and graph/tests/test_broken_waits_do_not_hide_forever.py stay green. The gate proves that `settled` and `Backlog.ready()` use both sources together and that each one alone can keep a parent open. It fails on today's tree, where the `sliced_from` pieces are ignored. It does not prove anything about `doctor`, about `frontier.startable`, or about how a piece is written.

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


def both_sources(a_status, piece_status):
    """P names card A in its own Needs and is also named by P.one in sliced_from."""
    where = pathlib.Path(tempfile.mkdtemp())
    note(where / "A", status=a_status, gate="true", files=["a.py"])
    note(where / "P", status="sliced", needs=["A"], gate="true")
    note(where / "P.one", status=piece_status, sliced_from="P", gate="true", files=["one.py"])
    note(where / "D", status="todo", needs=["P"], gate="true", files=["d.py"])
    return Backlog(where)


def ready_ids(book):
    return [row["id"] for row in book.ready()]


book = cut_by_hand("todo", "done")
rows = book.tasks()
assert "P" not in settled(rows), f"{RED}: P settled while P.one is todo"
assert "D" not in ready_ids(book), f"{RED}: D is ready while P.one is todo"

book = cut_by_hand("done", "dropped")
rows = book.tasks()
assert "P" in settled(rows), \
    f"{RED}: {sorted(settled(rows))} leaves out P although P.one is done and P.two dropped"
assert "D" in ready_ids(book), \
    f"{RED}: D is not ready although both pieces of P are finished"

# Both sources count together. Its own Needs is finished, a card naming it is
# not: a fallback that reads sliced_from only when Needs is empty settles P here.
book = both_sources("done", "todo")
rows = book.tasks()
assert "P" not in settled(rows), \
    f"{RED}: P settled while P.one is todo, because its own Needs is done"
assert "D" not in ready_ids(book), f"{RED}: D is ready while P.one is todo"

# The other way round: a card naming it is finished, its own Needs is not.
book = both_sources("todo", "done")
rows = book.tasks()
assert "P" not in settled(rows), \
    f"{RED}: P settled while the card in its own Needs is todo"
assert "D" not in ready_ids(book), f"{RED}: D is ready while A is todo"

# Both finished: settled, and only then is D ready.
book = both_sources("done", "done")
rows = book.tasks()
assert "P" in settled(rows), f"{RED}: P not settled although both sources are done"
assert "D" in ready_ids(book), f"{RED}: D is not ready although both sources are done"

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
