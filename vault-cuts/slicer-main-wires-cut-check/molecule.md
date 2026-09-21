---
source:
- docs/rfc/jev-cuts-brief.md:62
- docs/rfc/jev-cuts-brief.md:65
- docs/rfc/jev-cuts-brief.md:70
files:
- slicer/slicer.py
- slicer/tests/test_slicer_main_cut_check.py
gate_files_are_the_work: true
may_add_files: true
status: done
sliced_atoms: d39c86da66a22d80
requirement:
  goal: slicer.main passes run_answer a checker built from the campaign's decisions-model check, so the
    check runs before the review is paid for whenever the slicer is given a campaign.
  done_when: With --campaign, slicer.main calls run_answer with a callable checker keyword. Without --campaign,
    it passes checker=None or no checker. The test proves only what is passed to run_answer, not what
    the check decides.
  sources:
  - docs/rfc/jev-cuts-brief.md:62
  - docs/rfc/jev-cuts-brief.md:65
  - docs/rfc/jev-cuts-brief.md:70
contract_seen: 93cc8f6325054038
accepted_criteria:
  goal: slicer.main passes run_answer a checker built from the campaign's decisions-model check, so the
    check runs before the review is paid for whenever the slicer is given a campaign.
  gate: 'set -e -o pipefail

    (cd slicer/tests && timeout 600 python3 -m unittest test_slicer_main_cut_check)

    '
  done_when: With --campaign, slicer.main calls run_answer with a callable checker keyword. Without --campaign,
    it passes checker=None or no checker. The test proves only what is passed to run_answer, not what
    the check decides.
  files:
  - slicer/slicer.py
  - slicer/tests/test_slicer_main_cut_check.py
rebuild_from: /var/tmp/graph-trees/graph-fgl_gva6/task-slicer-main-wires-cut-check
session: e3f8bb07-5137-4787-8586-4ad579085cf0
session_account: personal
rebuild_round: 2
rejections:
- 'Diff line 22 (goal): The recording wrapper fails before calling the decisions model. — repo is a pathlib.Path,
  but cut_record.recording calls space.artifact and space.event. recording(repo, decide) therefore raises
  AttributeError before decide runs. cut_check._ask_all catches that exception and skips the question,
  so the campaign checker produces no model verdicts.

  Diff line 22 (note): The checker receives the target ID instead of the required target card as its wall.
  — The note explicitly requires wall=target. main resolves target to the card dictionary, but passes
  args.target, a string. cut_questions.for_atoms forwards wall into the model state as the recorded information
  about the replaced card, so this wiring omits that card''s contents.'
- 'Diff line 32 (note): make_checker receives the campaign Workspace as space instead of the required
  repository path. — The note explicitly requires ''repo as space''. This line passes space, assigned
  Workspace(campaign) on line 31. cut_hook.make_checker forwards that argument unchanged to cut_check.check.
  Use make_checker(campaign, repo, recording(space, decide), wall=target), preserving the Workspace for
  recording.'

commit: aca3672ef125775c777bc025d1f08c3c2d8e17a1
worktree: /var/tmp/graph-trees/graph-fgl_gva6/task-slicer-main-wires-cut-check
kept_at: '2026-09-20T16:43:49Z'
---

## Goal

slicer.main passes run_answer a checker built from the campaign's decisions-model check, so the check runs before the review is paid for whenever the slicer is given a campaign.

## Why

The pieces of the check exist as separate cards, but nothing in the slicer's entry point hands the checker to run_answer, so the switch has no effect.

## Done when

With --campaign, slicer.main calls run_answer with a callable checker keyword. Without --campaign, it passes checker=None or no checker. The test proves only what is passed to run_answer, not what the check decides.

## Gate

```sh
set -e -o pipefail
(cd slicer/tests && timeout 600 python3 -m unittest test_slicer_main_cut_check)

```

## Needs

- [[cut-hook/01-cut-hook-module]]
- [[cut-check-in-the-slicer/01-run-answer-runs-the-checker]]
- [[cut-record/molecule]]
- [[decisions-door/01-decisions-ask]]

## Uses

- [[slicer/slicer.py:main]]
- [[slicer/slicer_answer.py:run_answer]]

## Note

Files. slicer/slicer.py is edited. slicer/tests/test_slicer_main_cut_check.py is new.
In main, when args.campaign is set, build the checker and pass it to run_answer as checker=.
Build it with make_checker from slicer/cut_hook.py, which an earlier card creates. Give it the campaign path, repo as space, the decisions-model ask wrapped by the recording wrapper in slicer/cut_record.py (read that file for its name), and wall=target.
The decisions-model ask is the one in graph/lib/decisions.py.
Without args.campaign, pass checker=None, so behaviour is exactly as today.
Do not change how the card is published or refused.
The test must not import cut_hook directly. It patches slicer.run_answer (slicer.py imports it into its own namespace), runs main with --answer and --campaign against a small repo, and records the kwargs run_answer is called with.
The test asserts a callable checker is passed with --campaign and checker is None without it.
Today the assertion fails, because main passes no checker.
