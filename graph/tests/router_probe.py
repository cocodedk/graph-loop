"""A deterministic Decisions API response, never a paid model call."""

import io
import json


class Decisions:
    def __init__(self, model="claude-opus-5", effort="medium", confidence=0.95,
                 choice=None, unavailable=False):
        self.model, self.effort, self.confidence = model, effort, confidence
        self.choice, self.unavailable = choice, unavailable
        self.requests = []

    def __call__(self, request, **kwargs):
        if self.unavailable:
            raise TimeoutError("decision service unavailable")
        body = json.loads(request.data)
        self.requests.append(body)
        answers = {}
        for name, question in body["questions"].items():
            criteria = question["criteria"]
            offered = [(key, str(value)) for key, value in criteria.items()]
            choice = self.choice or next((key for key, value in offered
                if self.model in key + value and self.effort in key + value), "not-offered")
            answers[name] = {"type": "choice", "choice": choice,
                "confidence": self.confidence,
                "probabilities": {key: float(key == choice) for key in criteria}}
        return io.BytesIO(json.dumps({"answers": answers,
            "usage": {"input_tokens": 20, "output_tokens": 1, "cost": 0.001}}).encode())


CATALOG = {"GRAPH_ACCOUNTS": "work", "GRAPH_BUILDERS": "claude-sonnet-5,claude-opus-5",
           "GRAPH_REVIEWERS": "gpt-6-astra,gpt-5.6-sol",
           "GRAPH_CLAUDE_REVIEWERS": "claude-opus-5,claude-sonnet-5"}
CARD = {"id": "route-card", "goal": "repair a small helper", "files": ["a.py"],
        "gate": "true", "done_when": "a focused regression passes", "status": "todo"}
