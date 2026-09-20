"""What makes two failures the same: everything a rerun changes, blanked.

Split from `triage_signatures` at the 200-line cap. That module is still the
front door — `from triage_signatures import stable` — and TRIAGE's own cause
key reads failures through it, so there is one home for this rule rather than
a copy of it in each reader.

What is blanked is what a rerun changes on its own. Everything else is the
failure: filenames, the directories under the checkout, and the line inside a
file. Blanking any of those merges two failures into one, which parks a card
as a spin for something it never did and refuses the second failure the
recovery grant it never spent.
"""

from __future__ import annotations

import re

# The checkout the round ran in. `Worktree` cuts `mkdtemp(prefix="drive-")`
# under whatever TMPDIR the driver was given — which itself nests — and puts
# `task-<id>` inside it. The match starts where a PATH starts and stops at the
# FIRST such pair, so only the prefix goes and everything under it is kept:
# `pkg/drive-cache/task-one` is a directory somebody wrote, and a greedy
# parent match ate it and left one failure where there were two.
#
# A path starts after anything that is not part of a name — a space, a quote,
# a bracket — or after the `//` of a `file://` URI, and nowhere else. Both,
# named separately: dropping the slash from the first to let the URI in also
# let a doubled slash start a path, so `pkg//drive-cache/task-one` became a
# checkout and two directories somebody wrote came out as one failure.
START = r"(?:(?<![\w./-])|(?<=file://))"
CHECKOUT = re.compile(START + r"(?:/[\w.-]+)*?/drive-[^/\s]+/task-[^/\s]+")
# The empty home a gate is given: `gates.py` cuts a fresh one per run.
GATE_HOME = re.compile(START + r"(?:/[\w.-]+)*?/gate-home-[^/\s]*")
# A port belongs to an address, never to a file. Behind a URL scheme the host
# may be a name, an IPv4 or a bracketed IPv6; without one, only `localhost`
# and a numeric host are addresses — the ephemeral ports a log prints bare.
# `a.py:44` and `a.py:55` stay two failures.
URL_PORT = re.compile(r"(?<=://)(\[[0-9a-fA-F:]+\]|[\w.-]+):\d{2,5}\b")
BARE_PORT = re.compile(r"\b(localhost|\d{1,3}(?:\.\d{1,3}){3}):\d{2,5}\b")
ELAPSED = re.compile(r"\b\d+(?:\.\d+)?s\b")


def stable(text: str) -> str:
    """This output with the checkout, the gate's home, the port of an address
    and an elapsed time blanked, and nothing else touched."""
    text = CHECKOUT.sub("<worktree>", text)
    text = GATE_HOME.sub("<gate-home>", text)
    text = URL_PORT.sub(r"\1:<port>", text)
    text = BARE_PORT.sub(r"\1:<port>", text)
    return ELAPSED.sub("<time>", text).strip()
