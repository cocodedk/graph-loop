---
files:
- slicer/cut_verdicts.py
- slicer/tests/test_cut_verdicts.py
may_add_files: true
gate_files_are_the_work: true
status: done
requirement:
  goal: Create slicer/cut_verdicts.py with Verdict(id, question, choice, confidence, usable), read(asked,
    answer, gate=0.6), merges(molecule, verdicts), findings(molecule, verdicts) and apply_merges(molecule,
    pairs). read takes any object with `id` and `questions` (a dict keyed by question id) as asked, and
    any object with `ok` and `answers` (a dict from question id to a dict with `choice` and `confidence`)
    as answer. It returns one Verdict per asked question that has an answer, and an empty list when answer.ok
    is false. A verdict is usable only when its confidence is a number at or above gate. merges returns
    an (atom, atom) pair for an adjacent pair of atoms only when a usable keep_together verdict for the
    question `cut` has an id containing both atom names and the two atoms share a file. findings returns
    one sentence per usable `fail` verdict, naming the atom whose name is in the verdict id and the question.
    apply_merges joins the second atom into the first, uniting files without duplicates, joining goals
    and done_whens, keeping both gates in order, and renumbers the stages from 1.
  done_when: The tests pass with scripted asked and answer objects. A verdict below 0.6 is not usable
    and produces no merge and no finding. A usable keep_together on atoms that share no file, or that
    are not adjacent, produces no merge. A usable fail names the atom and the question. apply_merges unites
    the files, keeps both gates in order and renumbers the stages. An answer with ok false gives no verdicts.
    Nothing raises.
  sources: []
contract_seen: 60ca656c9e7cf243
accepted_criteria:
  goal: Create slicer/cut_verdicts.py with Verdict(id, question, choice, confidence, usable), read(asked,
    answer, gate=0.6), merges(molecule, verdicts), findings(molecule, verdicts) and apply_merges(molecule,
    pairs). read takes any object with `id` and `questions` (a dict keyed by question id) as asked, and
    any object with `ok` and `answers` (a dict from question id to a dict with `choice` and `confidence`)
    as answer. It returns one Verdict per asked question that has an answer, and an empty list when answer.ok
    is false. A verdict is usable only when its confidence is a number at or above gate. merges returns
    an (atom, atom) pair for an adjacent pair of atoms only when a usable keep_together verdict for the
    question `cut` has an id containing both atom names and the two atoms share a file. findings returns
    one sentence per usable `fail` verdict, naming the atom whose name is in the verdict id and the question.
    apply_merges joins the second atom into the first, uniting files without duplicates, joining goals
    and done_whens, keeping both gates in order, and renumbers the stages from 1.
  gate: 'set -e -o pipefail

    (cd slicer/tests && timeout 600 python3 -m unittest test_cut_verdicts)

    '
  done_when: The tests pass with scripted asked and answer objects. A verdict below 0.6 is not usable
    and produces no merge and no finding. A usable keep_together on atoms that share no file, or that
    are not adjacent, produces no merge. A usable fail names the atom and the question. apply_merges unites
    the files, keeps both gates in order and renumbers the stages. An answer with ok false gives no verdicts.
    Nothing raises.
  files:
  - slicer/cut_verdicts.py
  - slicer/tests/test_cut_verdicts.py
rebuild_from: /var/tmp/graph-trees/graph-nfc0tbqj/task-cut-verdicts.cut-verdicts-module
session: 7ca9f076-b889-4845-ab45-0d283f59d242
session_account: personal
rejections:
- 'Diff line 97 (goal): apply_merges resolves absorbed names only once, so overlapping pairs can silently
  discard an atom''s files, goal, done_when and gate. — For atoms alpha, beta, gamma, delta, pass [(''beta'',''gamma''),
  (''alpha'',''beta''), (''gamma'',''delta'')]. After the first two merges, gamma maps to beta and beta
  maps to alpha. This line resolves gamma only to beta, so delta is joined into the already-absorbed beta.
  The final filtering removes beta and delta, leaving alpha without delta''s contents. These valid adjacent
  pairs violate the requirement to join each second atom into its first and preserve their combined contents.'

requeued: true
commit: 57abef5e7b6b873fda5a6db2dc666075aa9f6308
worktree: /var/tmp/graph-trees/graph-nfc0tbqj/task-cut-verdicts.cut-verdicts-module
kept_at: '2026-09-20T16:27:56Z'
---

## Goal

Create slicer/cut_verdicts.py with Verdict(id, question, choice, confidence, usable), read(asked, answer, gate=0.6), merges(molecule, verdicts), findings(molecule, verdicts) and apply_merges(molecule, pairs). read takes any object with `id` and `questions` (a dict keyed by question id) as asked, and any object with `ok` and `answers` (a dict from question id to a dict with `choice` and `confidence`) as answer. It returns one Verdict per asked question that has an answer, and an empty list when answer.ok is false. A verdict is usable only when its confidence is a number at or above gate. merges returns an (atom, atom) pair for an adjacent pair of atoms only when a usable keep_together verdict for the question `cut` has an id containing both atom names and the two atoms share a file. findings returns one sentence per usable `fail` verdict, naming the atom whose name is in the verdict id and the question. apply_merges joins the second atom into the first, uniting files without duplicates, joining goals and done_whens, keeping both gates in order, and renumbers the stages from 1.

## Done when

The tests pass with scripted asked and answer objects. A verdict below 0.6 is not usable and produces no merge and no finding. A usable keep_together on atoms that share no file, or that are not adjacent, produces no merge. A usable fail names the atom and the question. apply_merges unites the files, keeps both gates in order and renumbers the stages. An answer with ok false gives no verdicts. Nothing raises.

## Gate

```sh
set -e -o pipefail
(cd slicer/tests && timeout 600 python3 -m unittest test_cut_verdicts)

```

## Note

Only slicer/cut_verdicts.py and its test file are written. The module imports nothing from slicer/cut_questions.py or graph/lib/decisions.py, so the tests build the asked and answer objects themselves. The brief does not declare the id format, so tests use atom names that are not substrings of one another and put both names in the id.
