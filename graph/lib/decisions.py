"""Ask a decisions model several typed questions about one state, and read every answer or none.

One call carries every question, so the state is sent once. The reply is read the way
`provider_jev._read` reads it: closed JSON, no `error` beside `answers`, each answer only
the fields `provider_jev.ANSWER_FIELDS` names, each choice one of that question's own
criteria. Anything else is one refusal for the whole call, with what it cost, because a
half-read reply would let a caller act on some answers and guess the rest. Nothing here
raises: the caller falls back to its own way when `ok` is False.
"""

from __future__ import annotations

import dataclasses
import json
import os
import time
import urllib.request
from collections.abc import Callable

import provider_jev
from providers import closed_object


@dataclasses.dataclass
class Answer:
    ok: bool
    answers: dict = dataclasses.field(default_factory=dict)   # id -> {"choice", "confidence"}
    seconds: float = 0.0
    cost: float | None = None
    why: str = ""        # set whenever ok is False


class _Refused(ValueError):
    """A reply this loop will not read; its message is the reason."""


def ask(state: dict, questions: dict[str, dict],
        post: Callable[[str], str] | None = None) -> Answer:
    """`questions` maps an id to {"instructions": str, "criteria": {choice: description}}."""
    started = time.perf_counter()
    cost = None
    try:
        reply = (post or _post)(_body(state, questions))
        whole = json.loads(reply, object_pairs_hook=closed_object)
        cost = provider_jev._spend(whole).get("cost")   # a refused reply still cost money
        answers = _read(whole, questions)
    except Exception as error:   # noqa: BLE001 — every fault is a fall-back, never a dead turn
        why = str(error) if isinstance(error, _Refused) \
            else f"decisions call failed: {type(error).__name__}"
        return Answer(False, seconds=time.perf_counter() - started, cost=cost, why=why)
    return Answer(True, answers, time.perf_counter() - started, cost)


def _body(state: dict, questions: dict[str, dict]) -> str:
    """The request, with `default=str` because the state is evidence read from a card,
    where a YAML date is not worth a dead call."""
    if not questions:
        raise _Refused("no question to ask")
    expanded = {}
    for qid, one in questions.items():
        expanded.update(json.loads(provider_jev.question(
            state, one["criteria"], instructions=one["instructions"], qid=qid))["questions"])
    return json.dumps({"model": provider_jev.MODEL, "state": state, "questions": expanded},
                      ensure_ascii=False, default=str)


def _read(whole, questions: dict[str, dict]) -> dict[str, dict]:
    if not isinstance(whole, dict) or "error" in whole:
        raise _Refused("the reply is not an answer object, or carries an error")
    said = whole.get("answers")
    if not isinstance(said, dict) or set(said) != set(json.loads(_body({}, questions))["questions"]):
        raise _Refused("the reply does not answer exactly the questions asked")
    return {qid: _choice(qid, {"answers": {
        name: said[name] for name in json.loads(provider_jev.question(
            {}, one["criteria"], qid=qid))["questions"]}}, one["criteria"])
        for qid, one in questions.items()}


def _choice(qid: str, one, criteria: dict[str, str]) -> dict:
    answer = provider_jev._answer(one, tuple(criteria), qid)
    if answer is None:
        raise _Refused(f"{qid}: not a complete, unambiguous choice average")
    return {"choice": answer["choice"], "confidence": answer["confidence"]}


def _post(body: str) -> str:
    """The one call the tests never make. `provider_jev` keeps its own inline, so the
    endpoint, the timeout and the key are read from there and from the environment."""
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:      # otherwise the gateway in front of us attaches the one it holds
        headers["Authorization"] = f"Bearer {key}"
    call = urllib.request.Request(provider_jev.URL, data=body.encode(), headers=headers)
    with urllib.request.urlopen(call, timeout=provider_jev.TIMEOUT) as reply:
        return reply.read().decode("utf-8", "replace")
