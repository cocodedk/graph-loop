"""The reviewer of one lean change: a first build's diff against main, or a revise round's diff with the
review threads it answers."""

from __future__ import annotations

import os

import lean_calls
import providers
import review
from review_scope import VERDICT

CODEX_BIN = os.environ.get("GRAPH_CODEX", "codex")
THREADS_LIMIT = 6000   # characters of the threads' text the reviewer reads


def judge(ws, feature: str, spec: str, diff: str, cwd: str, threads: str = "") -> providers.Outcome:
    """`threads` is a revise round's review threads: the change must fix each one."""
    prompt = (f"You review one change to this repository, read-only. It should implement the "
              f"spec below, with tests. Refuse only for: something the spec's 'Done when' or "
              f"acceptance tests name that does not hold, any defect you can name (wrong for some "
              f"real input or use), a security hole, behaviour added without tests, or a file the spec "
              f"does not call for that nothing uses (name it). Accept, listing findings, only for "
              f"style, a stated limit or a suggestion. In this review an ACCEPT may carry findings, "
              f"whatever the answer rule below says.\n\n"
              f"## Spec\n\n{spec}\n\n" + (
                  f"## The diff this round made\n\n{diff}\n\n"
                  f"## The review threads this round answers\n\n{threads[:THREADS_LIMIT]}\n\n"
                  f"This round answers those threads on an open pull request. The change must fix each "
                  f"one: a thread whose defect is still unfixed in the diff is a reason to refuse.\n\n{VERDICT}"
                  if threads else f"## The diff against main\n\n{diff}\n\n{VERDICT}"))

    def paid(kind, account, cost, tokens, _text):
        ws.attempt(feature, account=account, kind=kind, cost=cost, tokens=tokens,
                   effort=use["effort"], purpose="review")
    use = lean_calls.started(ws, "review", feature)
    return review.codex(CODEX_BIN, prompt, cwd=cwd, effort=use["effort"], attempt=paid)
