"""The reviewer of one lean change: a first build's diff against main, or a revise round's diff with the
review threads it answers."""

from __future__ import annotations

import os
import pathlib

import jev
import lean_calls
import lean_shorten
import providers
import review
from review_scope import NOTED_VERDICT

CODEX_BIN = os.environ.get("GRAPH_CODEX", "codex")
PROMPT_LIMIT = 900000  # characters; Codex refuses 1048576 and needs room for its own framing
THREADS_LIMIT = 6000   # characters of the threads' text the reviewer reads
JEV_LIMIT = 50000      # characters of diff Jev reads; a longer diff goes straight to Codex
CHECK = {"accept": "The diff implements the spec, and tests cover what it changes: its own, or the existing "
                   "tests it leaves in place for a change that keeps behaviour.",
         "no_tests": "The diff adds new behaviour (a new feature, input, output or rule) and neither adds nor "
                     "changes any test for it.",
         "wrong_spec": "The diff does not implement this spec: it does something else.",
         "unknown": "The evidence cannot show which: for example, tests outside the diff may already cover "
                    "the change."}
FOUND = {"no_tests": "The diff adds new behaviour and no test for it (Jev).",
         "wrong_spec": "The diff does not implement this spec (Jev)."}


def refused(ws, feature: str, spec: str, diff: str, cwd: str) -> str:
    """Jev's finding when it is sure the diff has no tests or is for another spec, else "". It may only
    refuse: measured, it cannot tell a correct diff from a subtly wrong one, so an accept is Codex's."""
    if len(diff) > JEV_LIMIT:
        return ""
    rules = jev.read(pathlib.Path(cwd) / "CLAUDE.md")   # the reviewer's own evidence; never the lessons
    said = jev.choose(ws, feature, "review", {"spec": spec, "rules": rules, "diff": diff},
                      {"verdict": "Does this diff implement the spec, with tests?"}, CHECK).get("verdict")
    return next((found for choice, found in FOUND.items() if said and jev.sure(said, choice)), "")


def judge(ws, feature: str, spec: str, diff: str, cwd: str, threads: str = "") -> providers.Outcome:
    """`threads` is a revise round's review threads: the change must fix each one. A first build's diff
    that Jev surely refuses is refused without paying Codex."""
    if not threads and (found := refused(ws, feature, spec, diff, cwd)):
        return providers.Outcome("ok", text=found, verdict="REJECT", findings=(found,))
    def ask(shown: str) -> str:
        return (f"You review one change to this repository, read-only. It should implement the "
                f"spec below, with tests. Refuse only for: something the spec's 'Done when' or "
                f"acceptance tests name that does not hold, any defect you can name (wrong for some "
                f"real input or use), a security hole, behaviour added without tests, or a file the spec "
                f"does not call for that nothing uses (name it). Accept, listing findings, only for "
                f"style, a stated limit or a suggestion, and among those name any existing function the "
                f"change should reuse instead of its own, and why; such a finding never refuses.\n\n"
                f"## Spec\n\n{spec}\n\n" + (
                    f"## The diff this round made\n\n{shown}\n\n"
                    f"## The review threads this round answers\n\n{threads[:THREADS_LIMIT]}\n\n"
                    f"This round answers those threads on an open pull request. The change must fix each "
                    f"one: a thread whose defect is still unfixed in the diff is a reason to refuse.\n\n{NOTED_VERDICT}"
                    if threads else f"## The diff against main\n\n{shown}\n\n{NOTED_VERDICT}"))

    prompt = ask(diff)
    if len(prompt) > PROMPT_LIMIT:
        prompt = ask(lean_shorten.shorten(diff, PROMPT_LIMIT - len(ask(""))))

    def paid(kind, account, cost, tokens, _text):
        ws.attempt(feature, account=account, kind=kind, cost=cost, tokens=tokens,
                   effort=use["effort"], purpose="review")
    use = lean_calls.started(ws, "review", feature)
    return review.codex(CODEX_BIN, prompt, cwd=cwd, effort=use["effort"], attempt=paid)
