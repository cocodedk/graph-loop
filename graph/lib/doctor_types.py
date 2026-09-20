"""The shape a complaint takes, shared by the doctor and its checks."""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class Complaint:
    about: str
    what: str
    do: str
