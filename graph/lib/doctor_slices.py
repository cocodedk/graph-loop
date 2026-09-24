"""A `sliced` card that nothing can ever settle."""

from __future__ import annotations

from doctor_types import Complaint


def check_orphan_slices(tasks: list[dict], parents: set) -> list[Complaint]:
    """A `sliced` card is settled through its `Needs` or through a card that
    names it in `sliced_from`. With neither, nothing can ever settle it."""
    return [Complaint(
        row.get("id", "?"), "it is `sliced` but has no needs and no card names it "
        "in `sliced_from`, so nothing can ever settle it",
        "cut its pieces with `sliced_from` naming it, or put them in its needs")
        for row in tasks
        if row.get("status") == "sliced" and not row.get("needs")
        and row.get("id") not in parents]
