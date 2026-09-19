"""A combined gate's full result and the commits that result can speak for."""

from __future__ import annotations

from dataclasses import dataclass

from gates import GateResult


@dataclass
class GateFailure:
    gate: str
    result: GateResult
    commit: str
    checkout: str

class CombinedGateFailed(RuntimeError):
    """A candidate failed; its exact parent is the only baseline for attribution."""

    def __init__(self, message: str, gate: str = "", *, base: str = "",
                 failure: GateFailure | None = None) -> None:
        super().__init__(message)
        self.gate, self.base, self.failure = gate, base, failure


class GateMutatedTree(CombinedGateFailed):
    """A gate changed the tree it judged and cannot prove anything about the commit."""
