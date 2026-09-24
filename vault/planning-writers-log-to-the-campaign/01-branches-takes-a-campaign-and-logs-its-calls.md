---
files:
- slicer/branches.py
- slicer/tests/test_branches_campaign.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
---

## Goal

slicer/branches.py main accepts --campaign and sets intelligence.CAMPAIGN from it. A controlled reviewer refusal then leaves the findings whole in the campaign's artifact records.

## Done when

The new test calls branches.main with --campaign, a --brief file, a --vault inside --repo, and a --answer holding a valid BRANCHES answer in the shape test_branches.py already uses. intelligence.providers.codex is patched to refuse with a multi-line findings text. It asserts that calls/the slicer/001-review-answer.txt equals the findings exactly. It also asserts that a run without --campaign gives the same return code and writes no calls folder, and it resets intelligence.CAMPAIGN afterwards. It fails today because argparse rejects --campaign.

## Gate

```sh
set -e -o pipefail
cd slicer/tests
python3 -m unittest -q test_branches_campaign
cd ../..
ruff check slicer/branches.py slicer/tests/test_branches_campaign.py

```

## Uses

- [[slicer/intelligence.py:CAMPAIGN]]
- [[slicer/branches.py:def main]]

## Creates

- [[slicer/branches.py:--campaign]]

## Note

Only slicer/branches.py changes in code, and the new test file is the only file added. Do not add a new record folder or call slicer_state.record here. The prompts and answers are already the artifacts. Keep the file under 200 lines (158 today).
