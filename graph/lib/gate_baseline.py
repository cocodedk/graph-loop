"""Compare full gate evidence at the candidate and its captured parent."""

from __future__ import annotations

import json
import re

# How long a unittest run took is the one thing a rerun changes on its own, so
# only that value goes, and only inside a whole summary line: any other number
# in the output — a count, a line, a value an assertion printed — is evidence.
DURATION = re.compile(r"^(Ran \d+ tests? in )\d+(?:\.\d+)?s$", re.MULTILINE)


def _record(failure) -> dict:
    return {"commit": failure.commit, "checkout": failure.checkout,
            "code": failure.result.code, "kind": failure.result.kind,
            "output": failure.result.output}


def _identity(failure) -> tuple:
    output = failure.result.output
    if failure.checkout:
        output = output.replace(failure.checkout, "<checkout>")
    return failure.result.kind, failure.result.code, DURATION.sub(r"\1<seconds>s", output)


def same_failure(loop, task: dict, clash) -> bool | None:
    """Only identical completed failures establish that this work added nothing."""
    evidence = {"gate": clash.gate, "base": clash.base}
    try:
        if not clash.failure or not clash.base:
            raise RuntimeError("the candidate failure has no full result or captured parent")
        evidence["candidate"] = _record(clash.failure)
        if clash.failure.result.kind != "ran":
            raise RuntimeError("the candidate gate did not finish running")
        baseline = loop.keeper._combined_tree_red(task["id"], clash.base, [clash.gate])
        evidence["baseline"] = _record(baseline) if baseline else {"commit": clash.base, "passed": True}
        if baseline and baseline.result.kind != "ran":
            raise RuntimeError(f"the baseline gate did not finish running ({baseline.result.kind})")
        same = baseline is not None and _identity(baseline) == _identity(clash.failure)
        evidence["comparison"] = "same failure" if same else "different evidence"
        loop.space.event("gate_baseline_compared", task=task["id"], base=clash.base,
                         same_failure=same)
        return same
    except RuntimeError as no_proof:
        evidence["unavailable"] = str(no_proof)
        loop.space.event("gate_defect_unproved", task=task["id"], gate=clash.gate[:160],
                         base=clash.base, why=str(no_proof)[:200])
        return None
    finally:
        loop.space.artifact(task["id"], "combined-gate-evidence", json.dumps(evidence, indent=2))
