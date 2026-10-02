"""The grill: a reviewer reads the spec before anything is built, and Jev sorts what it asked.

The reviewer's questions go three ways (`jev.sort_questions`): the irrelevant are dropped, and when
none is the person's the builder's go on with the build as its open questions; otherwise every one left
is mailed to the person and the run stops. Without
Jev, or when Jev is unsure, every question is the person's, as before.
"""

from __future__ import annotations

import pathlib

import jev
import lean_calls
import review
from lean_body import grill_prompt
from lean_judge import CODEX_BIN
from lean_spec import lessons, slug


def grill(ws, repo: str, spec_paths: list[str], profile_path: str, earlier: str = "",
          final: bool = False) -> tuple[str, str]:
    """(the questions only a person can answer, the ones handed to the builder); both "" when the spec
    is clear. `final` is the round limit: the person's questions are handed on too, and said so."""
    specs = "\n\n".join(f"## {pathlib.Path(path).name}\n\n{pathlib.Path(path).read_text('utf-8')}"
                        for path in spec_paths)
    prompt = grill_prompt(profile_path, lessons(pathlib.Path(spec_paths[0]).parent), specs, earlier)

    def paid(kind, account, cost, tokens, _text):
        ws.attempt("grill", account=account, kind=kind, cost=cost, tokens=tokens,
                   effort=use["effort"], purpose="grill")
    use = lean_calls.started(ws, "grill", "grill")
    out = review.codex(CODEX_BIN, prompt, cwd=repo, effort=use["effort"], attempt=paid, job="grill")
    questions = "" if out.verdict == "ACCEPT" else (out.text or f"the grill did not answer ({out.kind})")
    asked, handed, dropped = questions, "", ""
    if questions and out.verdict == "REJECT":
        sorted_ = jev.sort_questions(ws, "grill", questions)
        dropped = jev.JOIN.join(sorted_["irrelevant"])
        if sorted_["person"]:   # a stop asks the builder's too, so none is lost
            asked, handed = jev.JOIN.join(sorted_["person"] + sorted_["builder"]), ""
        else:
            asked, handed = "", jev.JOIN.join(sorted_["builder"])
    ws.event("lean_grilled", verdict=out.verdict, outcome=out.kind, questions=asked[:2000], handed=handed[:2000],
             dropped=dropped[:2000], specs=[slug(p) for p in spec_paths])
    note = ((f"\n\nHanded to the builder to decide: {handed}" if handed else "")
            + (f"\n\nDropped as irrelevant: {dropped}" if dropped else ""))
    if asked and final and out.verdict == "REJECT":   # the round limit: the run goes on
        ws.mail_person("graph-loop is building with open questions", f"{asked}{note}\n\nThe round limit is "
                       "reached: building goes on with these unresolved. The builder decides each, and its "
                       "choices go in the pull request description. No answer is needed to continue.")
    elif asked:
        subject = ("graph-loop has questions before building" if out.verdict
                   else "graph-loop could not read the specs before building")
        ws.mail_person(subject, f"{asked}{note}\n\nAnswer them in the specs, then run again. Nothing was built.")
    elif handed or dropped:
        ws.mail_person("graph-loop is building with open questions", f"Every question the grill asked is the "
                       f"builder's to settle or changes nothing, so building goes on.{note}\n\nThe builder's "
                       "choices go in the pull request description. No answer is needed to continue.")
    return asked, handed
