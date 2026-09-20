"""Where one key's entry begins and ends in a note's front matter.

Asked of the YAML parser, never guessed. `cardfile.patch` used to find it with
a regex that read the value as "the key's line plus the lines under it starting
with space, tab or dash" — and `safe_dump` of a string holding a newline emits
a quoted scalar with a BLANK line in it, so the match stopped there and
orphaned the closing quote. The card then parsed as something subtly wrong, and
after a second write it did not parse at all, which took every card in the
vault with it (2026-09-18).

Splitting this out is what keeps `cardfile` the front door under the cap.
"""

from __future__ import annotations

import yaml  # type: ignore[import-untyped]


def entry(front: str, field: str) -> tuple[int, int] | None:
    """The span of `field`'s whole entry, or None when the key is not there."""
    if not front.strip():
        return None
    node = yaml.compose(front)
    if node is None or not hasattr(node, "value"):
        return None
    for key, value in node.value:
        if getattr(key, "value", None) == field:
            stop = value.end_mark.index
            while stop > key.start_mark.index and front[stop - 1] in "\r\n":
                stop -= 1                     # the entry, never the break after it
            return key.start_mark.index, stop
    return None
