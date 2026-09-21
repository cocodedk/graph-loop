"""Write every decisions-model cut check into the campaign's log.

The wrapper only records. What the model said passes back unchanged, and it
never accepts or refuses a molecule; reading the answers is `cut_verdicts`.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

GRAPH_LIB = pathlib.Path(__file__).resolve().parents[1] / "graph" / "lib"
sys.path.insert(0, str(GRAPH_LIB))


def recording(space, ask, label: str = "cut-check"):
    """Return `ask` wrapped so each call leaves a `cut_asked` event and the
    `cut-request` and `cut-answer` artifacts under the task id `label`."""

    def asked(state, questions):
        started = time.time()
        space.artifact(label, "cut-request",
                       json.dumps({"state": state, "questions": questions},
                                  indent=2, sort_keys=True, default=str))
        try:
            answer = ask(state, questions)
        except Exception as error:      # recorded, then raised again
            why = f"{type(error).__name__}: {error}"
            space.artifact(label, "cut-answer", json.dumps({"error": why}))
            space.event("cut_asked", task=label, ok=False,
                        seconds=round(time.time() - started, 3), cost=None,
                        why=why, questions=len(questions))
            raise
        space.artifact(label, "cut-answer",
                       json.dumps(getattr(answer, "answers", None),
                                  indent=2, sort_keys=True, default=str))
        space.event("cut_asked", task=label, ok=bool(getattr(answer, "ok", False)),
                    seconds=getattr(answer, "seconds", round(time.time() - started, 3)),
                    cost=getattr(answer, "cost", None),
                    why=getattr(answer, "why", ""), questions=len(questions))
        return answer

    return asked
