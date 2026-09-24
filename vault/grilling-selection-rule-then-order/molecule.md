---
source:
- vault/specs/grilling-opening-analysis-and-selection.md:47
- vault/specs/grilling-opening-analysis-and-selection.md:49
- vault/specs/grilling-opening-analysis-and-selection.md:54
- docs/rfc/grilling-stage-interfaces.md:23
may_add_files: true
files:
- grill/select.py
- grill/tests/test_select.py
gate_files_are_the_work: true
status: todo
gate_reviewed_first: true
sliced_atoms: b265d60620b6556c
---

## Goal

grill/select.py:next_question(analysis, record, after, chooser, state) picks the next question with no model call. It first applies a follow-up rule to the picked choice in after, and then falls back to the earliest eligible question in the recorded order. It returns Selection(question, chosen_by, request) with chosen_by set to rule or order.

## Why

Steps 1 and 2 of choosing the next question (spec items 6 to 8) are the part of selection that needs no judgment. The chooser path stays open for the routing specification.

## Done when

grill/tests/test_select.py passes. A question is eligible only when its prerequisites are all resolved in record, its own state is pending, and in_scope is true; an ineligible question is never returned. When after is {question, picked} and a follow_ups entry {when, ask} names picked and its ask target is eligible, next_question returns that target with chosen_by rule and makes no model call. When several eligible follow-ups name the same picked choice, the one earliest in analysis order.position is returned. When no follow-up applies, the earliest eligible question by order.position is returned with chosen_by order. The tests include a case where a follow-up sits later in the order than an eligible plain question and is still chosen. A follow-up whose target is ineligible is skipped and falls through to order. When no question is eligible, the function returns no question. When chooser and state are None it is never called.

## Gate

```sh
set -e -o pipefail
out=$(mktemp)
python -m pytest grill/tests/test_select.py -q > "$out" 2>&1 || { cat "$out"; exit 1; }
tail -n 3 "$out"

```

## Note

File boundary: only grill/select.py and grill/tests/test_select.py. grill/questions.py is not used or edited, and eligibility is computed inline from the declared analysis.yaml and decisions.yaml shapes. Add grill/__init__.py and grill/tests/__init__.py only if the sibling tasks have not already added them.
