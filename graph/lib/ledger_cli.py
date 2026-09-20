#!/usr/bin/env python3
"""Print the ledger for this campaign: when, which card, what came of it."""

from __future__ import annotations

import sys

import ledger
import where
from workspace import Workspace

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 40
    print(ledger.text(Workspace(where.campaign()).events(), limit=limit))
