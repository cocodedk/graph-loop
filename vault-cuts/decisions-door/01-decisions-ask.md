---
files:
- graph/lib/decisions.py
- graph/tests/test_decisions.py
may_add_files: true
gate_files_are_the_work: true
status: done
requirement:
  goal: 'Create graph/lib/decisions.py with Answer and ask(state, questions, post=None). ask builds one
    request body with the provider_jev model and one entry per question. It sends the body through the
    injected post callable (str body in, str response out). It reads the response as provider_jev._read
    does: closed JSON with no duplicate keys, an `answers` object keyed by question id, each answer restricted
    to provider_jev.ANSWER_FIELDS, and no `error` beside it. Each choice must be one of that question''s
    own criteria keys. Any failure returns ok=False with a why.'
  done_when: graph/tests/test_decisions.py runs with a scripted post and no network, and passes these
    cases. A well-formed body for two questions gives ok=True, one entry per question id, seconds greater
    than 0, and cost read from usage. A question missing from answers gives ok=False with a non-empty
    why. A choice outside that question's criteria gives ok=False. A duplicate key gives ok=False. An
    `error` beside answers gives ok=False. Malformed JSON gives ok=False. A post that raises gives ok=False
    and nothing escapes. The existing graph/tests/test_provider_jev.py and test_triage_jev.py stay green
    unchanged.
  sources: []
replans: 2
replan_history:
- The gate runs only test_decisions; it does not establish the frozen requirement that test_provider_jev
  and test_triage_jev stay green unchanged. Include both suites in the gate or name a recorded decision
  narrowing that requirement.; The required cases omit rejection of answer fields outside ANSWER_FIELDS.
  Require that assertion so the gate cannot pass with an open answer schema.; Neither provider
- The frozen requirement says test_provider_jev and test_triage_jev must stay green unchanged. This gate
  checks only that their files are unchanged; it never runs them, and the note names no recorded decision
  authorizing that weaker proof. Restore both test suites to the gate and their passing requirement to
  done-when.
contract_seen: c1053a4f521a9bd2
accepted_criteria:
  goal: Create graph/lib/decisions.py with Answer and ask(state, questions, post=None). ask builds one
    request body with the provider_jev model and one entry per question, sends it through the injected
    post callable (str body in, str response out), and reads the reply as provider_jev._read does. The
    reply must be closed JSON with no duplicate keys and an `answers` object keyed by question id. Each
    answer is limited to provider_jev.ANSWER_FIELDS, and no `error` may sit beside `answers`. Each choice
    must be one of that question's own criteria keys. Any failure returns ok=False with a non-empty why,
    and nothing escapes.
  gate: 'set -e -o pipefail

    (cd graph/tests && timeout 600 python3 -m unittest test_decisions)

    (cd graph/tests && python3 -c "import unittest, test_decisions; n = unittest.defaultTestLoader.loadTestsFromModule(test_decisions).countTestCases();
    assert n >= 8, n")

    (cd graph/tests && timeout 600 python3 -m unittest test_provider_jev)

    (cd graph/tests && timeout 600 python3 -m unittest test_triage_jev)

    (cd graph && test -z "$(git status --porcelain -- lib/provider_jev.py tests/test_provider_jev.py tests/test_triage_jev.py)")

    '
  done_when: graph/tests/test_decisions.py runs with a scripted post and no network. It has at least these
    eight cases, and all pass. (1) A well-formed body for two questions gives ok=True, one entry per question
    id in the request body, seconds greater than 0, and cost read from usage. (2) A question missing from
    answers gives ok=False with a non-empty why. (3) A choice outside that question's own criteria gives
    ok=False, including a choice that is valid for a different question in the same call. (4) A duplicate
    key gives ok=False. (5) An `error` beside answers gives ok=False. (6) Malformed JSON gives ok=False.
    (7) An answer carrying a field outside provider_jev.ANSWER_FIELDS gives ok=False, so an open answer
    schema cannot pass. (8) A post that raises gives ok=False and nothing escapes. In addition, test_provider_jev
    and test_triage_jev pass unchanged, and graph/lib/provider_jev.py, graph/tests/test_provider_jev.py
    and graph/tests/test_triage_jev.py have no edits.
  files:
  - graph/lib/decisions.py
  - graph/tests/test_decisions.py
rebuild_from: /var/tmp/graph-trees/graph-ugezyzt1/task-decisions-door.decisions-ask
session: 5913287a-d59e-4a2e-bca2-9d1307a2f59d
session_account: personal

requeued: true
commit: fc3f710d9b6009fca319afb76b371c83b49e2e9c
worktree: /var/tmp/graph-trees/graph-ugezyzt1/task-decisions-door.decisions-ask
kept_at: '2026-09-20T16:26:14Z'
---

## Goal

Create graph/lib/decisions.py with Answer and ask(state, questions, post=None). ask builds one request body with the provider_jev model and one entry per question, sends it through the injected post callable (str body in, str response out), and reads the reply as provider_jev._read does. The reply must be closed JSON with no duplicate keys and an `answers` object keyed by question id. Each answer is limited to provider_jev.ANSWER_FIELDS, and no `error` may sit beside `answers`. Each choice must be one of that question's own criteria keys. Any failure returns ok=False with a non-empty why, and nothing escapes.

## Done when

graph/tests/test_decisions.py runs with a scripted post and no network. It has at least these eight cases, and all pass. (1) A well-formed body for two questions gives ok=True, one entry per question id in the request body, seconds greater than 0, and cost read from usage. (2) A question missing from answers gives ok=False with a non-empty why. (3) A choice outside that question's own criteria gives ok=False, including a choice that is valid for a different question in the same call. (4) A duplicate key gives ok=False. (5) An `error` beside answers gives ok=False. (6) Malformed JSON gives ok=False. (7) An answer carrying a field outside provider_jev.ANSWER_FIELDS gives ok=False, so an open answer schema cannot pass. (8) A post that raises gives ok=False and nothing escapes. In addition, test_provider_jev and test_triage_jev pass unchanged, and graph/lib/provider_jev.py, graph/tests/test_provider_jev.py and graph/tests/test_triage_jev.py have no edits.

## Gate

```sh
set -e -o pipefail
(cd graph/tests && timeout 600 python3 -m unittest test_decisions)
(cd graph/tests && python3 -c "import unittest, test_decisions; n = unittest.defaultTestLoader.loadTestsFromModule(test_decisions).countTestCases(); assert n >= 8, n")
(cd graph/tests && timeout 600 python3 -m unittest test_provider_jev)
(cd graph/tests && timeout 600 python3 -m unittest test_triage_jev)
(cd graph && test -z "$(git status --porcelain -- lib/provider_jev.py tests/test_provider_jev.py tests/test_triage_jev.py)")

```

## Uses

- [[graph/lib/provider_jev.py:URL]]
- [[graph/lib/provider_jev.py:MODEL]]
- [[graph/lib/provider_jev.py:TIMEOUT]]
- [[graph/lib/provider_jev.py:ANSWER_FIELDS]]
- [[graph/lib/provider_jev.py:def _spend]]
- [[graph/lib/provider_jev.py:def _number]]
- [[graph/lib/providers.py:closed_object]]

## Creates

- [[graph/lib/decisions.py:class Answer]]
- [[graph/lib/decisions.py:def ask]]

## Note

Files are graph/lib/decisions.py and graph/tests/test_decisions.py only. provider_jev.py and triage_jev.py must not be edited (brief line 29). The wire shape is not new. provider_jev._answer already reads whole["answers"][id] with ANSWER_FIELDS and usage beside it, so ask reuses that shape and adds no fields and no new refusal kinds. provider_jev has no standalone post, because its urlopen is inline, so decisions.py carries its own thin default post using provider_jev.URL, the same headers and TIMEOUT. Tests never call the default, and always inject post. The `questions` argument is a dict of id to {"instructions": str, "criteria": {choice: description}}. Answer.answers maps id to {"choice", "confidence"}. Add no new GRAPH_* environment name. Keep the file under 200 lines, with its one job stated in the first docstring line.
