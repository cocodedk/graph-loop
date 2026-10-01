"""The reason a lean run stopped, cut for the log without losing its cause.

The cause sits at the start of the text ("The repair changed nothing. Read what the builder said, ..."), the
gate's verdict at its end, and the middle is bulk. The last 2000 characters alone hid the cause.
"""

from __future__ import annotations

LIMIT, HEAD, TAIL = 2000, 600, 1400


def cut(why: str) -> str:
    """`why` whole when it fits `LIMIT`; else its start, a marker with the exact count left out, its end."""
    if len(why) <= LIMIT:
        return why
    return f"{why[:HEAD]}\n[... {len(why) - HEAD - TAIL} characters left out ...]\n{why[-TAIL:]}"
