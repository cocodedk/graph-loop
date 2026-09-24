---
files:
- slicer/intelligence.py
- slicer/tests/test_intelligence_unlogged.py
may_add_files: true
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
---

## Goal

slicer/intelligence.py prints one message containing the text "nothing is being logged" the first time a model call is recorded while CAMPAIGN is None. It prints nothing on later calls, and creates no files.

## Done when

The new test sets intelligence.CAMPAIGN to None and drives intelligence._call twice, capturing stdout and stderr. It asserts the text "nothing is being logged" appears exactly once across both calls, and that a scratch working directory holds no new files afterwards. Today it fails because nothing is printed. With CAMPAIGN set, the test asserts no such message is printed.

## Gate

```sh
set -e -o pipefail
cd slicer/tests
python3 -m unittest -q test_intelligence_unlogged

```

## Creates

- [[slicer/intelligence.py:nothing is being logged]]

## Note

Only slicer/intelligence.py changes, and the once-per-process flag lives there. The test resets that flag itself between cases. Prompts, replies and the existing CAMPAIGN behaviour stay unchanged. The task has to stay under 200 lines per file.
