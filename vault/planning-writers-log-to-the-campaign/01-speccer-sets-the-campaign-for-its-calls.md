---
files:
- slicer/speccer.py
- slicer/tests/test_speccer_campaign.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
---

## Goal

slicer/speccer.py main sets intelligence.CAMPAIGN from --campaign when one is given. A controlled reviewer refusal then leaves an artifact with the findings character for character, and an attempt record with the reported cost or none.

## Done when

The new test calls speccer.main with --campaign, a --answer holding a valid SPEC answer, and intelligence.providers.codex patched, as ReviewRecords in slicer/tests/test_intelligence.py does, to refuse with a multi-line findings text. The campaign directory is one made by Workspace(...).init(goal=..., backlog=...). It asserts that calls/the slicer/001-review-answer.txt equals the findings exactly, and that the review attempt row has cost None when the patched provider reports none and the reported cost when it does. It resets intelligence.CAMPAIGN afterwards, and it fails before the change because no calls folder exists. It claims only that the flag reaches the record machinery and that a refusal is kept whole, not timing or the report command.

## Gate

```sh
set -e -o pipefail
cd slicer/tests
python3 -m unittest -q test_speccer_campaign
cd ../..
ruff check slicer/speccer.py slicer/tests/test_speccer_campaign.py

```

## Uses

- [[slicer/intelligence.py:CAMPAIGN]]
- [[slicer/intelligence.py:def review]]

## Creates

- [[slicer/speccer.py:intelligence.CAMPAIGN]]

## Note

Only slicer/speccer.py changes in code, and the new test file is the only file added. Do not touch the .speccer-calls behaviour with no campaign. Deferred to later molecules: the "the slicer" task name that hides which layer a call belongs to, a literal start time, the report by layer, and the one-time "nothing is being logged" message.
