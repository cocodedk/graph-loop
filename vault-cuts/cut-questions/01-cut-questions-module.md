---
files:
- slicer/cut_questions.py
- slicer/tests/test_cut_questions.py
gate_files_are_the_work: true
may_add_files: true
status: done
requirement:
  goal: 'Create slicer/cut_questions.py with Asked(id, state, questions), for_cuts(molecule) and for_atoms(molecule,
    wall=None). The molecule is a dict whose `atoms` is a list of atom dicts. Asked.questions is a dict
    from question id to {type: ''choice'', instructions, criteria}, the same per-question shape provider_jev.question
    puts on the wire, where criteria maps each choice key to a description. for_cuts gives one Asked per
    adjacent pair of atoms. Its state holds the two atom dicts as written, and it asks one question, `cut`,
    with criteria keys split, keep_together and insufficient_evidence. for_atoms gives one Asked per atom.
    Its state holds the atom, plus the wall exactly as passed under the key `wall` only when wall is not
    None. It asks three questions, one_job, claims_only_what_is_proved and files_sufficient, each with
    criteria keys pass, fail and insufficient_evidence. Every Asked id is distinct and names the atom
    or atoms it is about. The module never raises on a molecule with zero or one atoms.'
  done_when: test_cut_questions passes and asserts all of the following on scripted molecules. A three-atom
    molecule gives two cut Asked, with distinct ids that name both atoms, whose state holds exactly the
    two adjacent atom dicts unchanged, and whose only question is `cut` with criteria keys exactly {split,
    keep_together, insufficient_evidence}. Molecules with zero or one atoms give no cut Asked. for_atoms
    gives one Asked per atom with distinct ids, and exactly the three named questions whose criteria keys
    are exactly {pass, fail, insufficient_evidence}. The atom state has no `wall` key when wall is None
    and carries the given wall value unchanged when it is passed.
  sources: []
replans: 1
replan_history:
- 'The required assertions omit the question wire shape: type must be ''choice'', instructions must be
  present, and criteria values must be descriptions. The gate could pass with malformed questions.; The
  required for_atoms assertions omit checking that state holds the atom unchanged and that each Asked
  id names its atom. The frozen goal requires both, and the note records no decision narrowing them.'
contract_seen: 0cef34af0a93494e
accepted_criteria:
  goal: 'Create slicer/cut_questions.py, which turns a molecule (a dict whose `atoms` is a list of atom
    dicts) into the questions a decisions model is asked. Asked(id, state, questions) is the unit. Asked.questions
    maps a question id to {type: ''choice'', instructions, criteria}, where criteria maps each choice
    key to a description string. for_cuts(molecule) gives one Asked per adjacent pair of atoms. Its state
    holds the two atom dicts as written. It asks one question, `cut`, with criteria keys split, keep_together
    and insufficient_evidence. for_atoms(molecule, wall=None) gives one Asked per atom. Its state holds
    the atom as written, plus the wall exactly as passed under the key `wall` only when wall is not None.
    It asks three questions, one_job, claims_only_what_is_proved and files_sufficient, each with criteria
    keys pass, fail and insufficient_evidence. Every Asked id is distinct and contains the `id` of each
    atom it is about. Neither function raises on a molecule with zero or one atoms.'
  gate: 'set -e -o pipefail

    (cd slicer/tests && timeout 600 python3 -m unittest test_cut_questions)

    (cd slicer/tests && timeout 120 python3 -c "import unittest, test_cut_questions as t; n = unittest.defaultTestLoader.loadTestsFromModule(t).countTestCases();
    assert n >= 1, n")

    (cd slicer && timeout 60 python3 -c "import cut_questions as c; assert all(hasattr(c, k) for k in
    (''Asked'', ''for_cuts'', ''for_atoms''))")

    '
  done_when: 'test_cut_questions passes, and it asserts all of the following on scripted molecules whose
    atoms carry distinct `id` values. For every question in every Asked from both functions: type == ''choice'',
    instructions is a non-empty string, and criteria is a dict whose values are all non-empty strings.
    A three-atom molecule gives exactly two cut Asked. Their ids are distinct, and each contains the `id`
    of both of its atoms. Their state holds exactly the two adjacent atom dicts, equal to the input and
    not mutated (compare against a deep copy taken before the call). Their only question is `cut`, with
    criteria keys exactly {split, keep_together, insufficient_evidence}. Molecules with zero atoms and
    with one atom give an empty list from for_cuts, and for_atoms on them does not raise (zero atoms gives
    an empty list, one atom gives one Asked). For a three-atom molecule, for_atoms gives exactly three
    Asked. Their ids are distinct and each contains its atom''s `id`. Each state''s atom equals the input
    atom, unmutated. The question keys are exactly {one_job, claims_only_what_is_proved, files_sufficient},
    each with criteria keys exactly {pass, fail, insufficient_evidence}. The atom state has no `wall`
    key when wall is None or omitted. It carries the given wall unchanged (same value, tested with a dict
    and with a falsy non-None value such as an empty dict) when passed.'
  files:
  - slicer/cut_questions.py
  - slicer/tests/test_cut_questions.py
rebuild_from: /var/tmp/graph-trees/graph-q_056hta/task-cut-questions.cut-questions-module
session: f446cfca-3b26-4645-bfcb-4e56486810f9
session_account: personal
rejections:
- 'Diff line 34 (goal): Cut Asked IDs can collide despite all atom IDs being distinct, violating the requirement
  that every Asked ID is distinct. — For {''atoms'': [{''id'': ''a''}, {''id'': ''b:c''}, {''id'': ''a:b''},
  {''id'': ''c''}]}, the first and third adjacent pairs both produce ''cut:a:b:c''. The contract places
  no restriction on colons in atom IDs.'

requeued: true
commit: 6c590c273855994903452eb72b3ddff85606c8d6
worktree: /var/tmp/graph-trees/graph-q_056hta/task-cut-questions.cut-questions-module
kept_at: '2026-09-20T16:25:41Z'
---

## Goal

Create slicer/cut_questions.py, which turns a molecule (a dict whose `atoms` is a list of atom dicts) into the questions a decisions model is asked. Asked(id, state, questions) is the unit. Asked.questions maps a question id to {type: 'choice', instructions, criteria}, where criteria maps each choice key to a description string. for_cuts(molecule) gives one Asked per adjacent pair of atoms. Its state holds the two atom dicts as written. It asks one question, `cut`, with criteria keys split, keep_together and insufficient_evidence. for_atoms(molecule, wall=None) gives one Asked per atom. Its state holds the atom as written, plus the wall exactly as passed under the key `wall` only when wall is not None. It asks three questions, one_job, claims_only_what_is_proved and files_sufficient, each with criteria keys pass, fail and insufficient_evidence. Every Asked id is distinct and contains the `id` of each atom it is about. Neither function raises on a molecule with zero or one atoms.

## Done when

test_cut_questions passes, and it asserts all of the following on scripted molecules whose atoms carry distinct `id` values. For every question in every Asked from both functions: type == 'choice', instructions is a non-empty string, and criteria is a dict whose values are all non-empty strings. A three-atom molecule gives exactly two cut Asked. Their ids are distinct, and each contains the `id` of both of its atoms. Their state holds exactly the two adjacent atom dicts, equal to the input and not mutated (compare against a deep copy taken before the call). Their only question is `cut`, with criteria keys exactly {split, keep_together, insufficient_evidence}. Molecules with zero atoms and with one atom give an empty list from for_cuts, and for_atoms on them does not raise (zero atoms gives an empty list, one atom gives one Asked). For a three-atom molecule, for_atoms gives exactly three Asked. Their ids are distinct and each contains its atom's `id`. Each state's atom equals the input atom, unmutated. The question keys are exactly {one_job, claims_only_what_is_proved, files_sufficient}, each with criteria keys exactly {pass, fail, insufficient_evidence}. The atom state has no `wall` key when wall is None or omitted. It carries the given wall unchanged (same value, tested with a dict and with a falsy non-None value such as an empty dict) when passed.

## Gate

```sh
set -e -o pipefail
(cd slicer/tests && timeout 600 python3 -m unittest test_cut_questions)
(cd slicer/tests && timeout 120 python3 -c "import unittest, test_cut_questions as t; n = unittest.defaultTestLoader.loadTestsFromModule(t).countTestCases(); assert n >= 1, n")
(cd slicer && timeout 60 python3 -c "import cut_questions as c; assert all(hasattr(c, k) for k in ('Asked', 'for_cuts', 'for_atoms'))")

```

## Creates

- [[slicer/cut_questions.py:Asked]]
- [[slicer/cut_questions.py:for_cuts]]
- [[slicer/cut_questions.py:for_atoms]]

## Note

Only slicer/cut_questions.py is created here, together with its test. No existing file is touched. The wall's shape is not declared anywhere, so it is passed through verbatim and the test uses an opaque value.
