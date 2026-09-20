"""The one closed shape accepted from TRIAGE's durable decision record."""

from __future__ import annotations

from triage_signatures import VERDICTS

FIELDS = {
    "at", "kind", "task", "verdict", "signature", "why", "repairable",
    "catchup", "accepted", "closed_at", "closed_index", "closed_kind",
}


def valid_decision(row: dict) -> bool:
    if set(row) - {"turn"} != FIELDS or row.get("kind") != "triage_decision":
        return False
    verdict, signature = row.get("verdict"), row.get("signature")
    common = (isinstance(row.get("at"), str)
              and isinstance(row.get("task"), str)
              and isinstance(row.get("why"), str)
              and type(row.get("repairable")) is bool
              and type(row.get("catchup")) is bool
              and type(row.get("accepted")) is bool
              and isinstance(row.get("closed_at"), str)
              and type(row.get("closed_index")) is int
              and row["closed_index"] >= 0
              and isinstance(row.get("closed_kind"), str))
    if not common:
        return False
    if verdict is None:
        return signature is None and not row["repairable"]
    return (verdict in VERDICTS and isinstance(signature, str) and bool(signature)
            and not row["accepted"])
