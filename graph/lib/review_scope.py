"""The answer a diff reviewer must give before a finding reaches a builder."""
from __future__ import annotations

import json
import re

from distress import closed_object

REQUIREMENTS = {"goal", "done_when", "gate", "note", "safety", "simplicity"}
# The exact shape `review._json_verdict` will accept, for the prompts that ask
# for it. It lives here, next to its parser, because for a year four prompts
# said only "the graph review JSON: review, accept boolean, findings list" and
# a reviewer that obeyed those words and wrote findings as OBJECTS had a
# correct REJECT thrown away as malformed (2026-09-18). A prompt and a parser
# that state the shape separately will drift; these two cannot.
VERDICT = (
    'Answer with exactly one JSON object on one line and no other text: '
    '{"review":"ACCEPT|REJECT","accept":true,"findings":["what is wrong, in one sentence"]}. '
    'Exactly those three keys. `findings` holds at most three plain strings, never objects. '
    'ACCEPT requires accept=true and no findings; REJECT requires accept=false and at '
    'least one finding.')


INSTRUCTION = """Review only this change against its accepted contract. Read direct callers or
existing shared rules only to establish a consequence of this diff; do not audit the
repository. A rule this repository already has somewhere else matters only when
this change duplicates it: name the module it should have followed and show why.
A blocking finding must identify an actual changed line in the numbered diff,
name the requirement it violates, and give concrete evidence. Pre-existing defects,
unrelated improvements and optional cleanup belong only in observations. They do
not reject this change or expand its task. When the contract is met and there is no
blocking defect, ACCEPT and stop. Never loosen tests or ignore safety boundaries.
Answer with one review JSON object before the distress line:
{"review":"ACCEPT|REJECT","accept":true,"findings":[{"diff_line":1,
"requirement":"goal|done_when|gate|note|safety|simplicity","problem":"what fails",
"evidence":"why this changed line violates that requirement"}],"observations":[]}
At most three findings and three observations (nonempty strings). ACCEPT requires
accept=true and no findings; REJECT requires accept=false and at least one finding.
diff_line is the numbered diff line, not the source file line. Headers and context
cannot anchor a finding; added and deleted lines inside a hunk can. For a metadata
or binary change, anchor its mode, rename/copy, Binary files or GIT binary patch
line under the Git diff header. File headers, index and similarity lines cannot.
"""


OBSERVATIONS = 3
LEGACY = re.compile(r"^[ \t]*REVIEW:[ \t]*(?:ACCEPT|REJECT)\b", re.MULTILINE)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _one_answer(text: str) -> object:
    """The reply's single JSON object, whatever prose sits around it.

    The prompt asks for one object and no other text, and for a year this read
    the whole reply, so a model that obeyed everything except that sentence lost
    its verdict: a ```json fence, a line of preamble or a closing sentence is a
    `JSONDecodeError`, which is `malformed`, which is a harness fault, which
    stood a driver down. Two of five diff reviews in one campaign went that way
    (2026-09-18). A fence is the commonest way a model emits JSON and no
    instruction reliably stops it; reading the object it did write refuses
    nothing that was ever valid, because every check below still runs on it.

    What prose does NOT buy is a second answer. Another object, or a legacy
    `REVIEW: ACCEPT` line beside this one, refuses the reply whole — agreeing or
    not, because a reviewer that wrote two answers has not decided which
    contract it answered.
    """
    start = text.find("{")
    if start < 0:
        raise ValueError("expected one scoped review object")
    body, end = json.JSONDecoder(object_pairs_hook=closed_object).raw_decode(text, start)
    around = text[:start] + text[end:]
    if "{" in around or LEGACY.search(around):
        raise ValueError("the reply holds more than one answer")
    return body


def read(text: str) -> dict:
    """Read one closed answer; neither prose nor an older verdict is a fallback."""
    body = _one_answer(text)
    if not isinstance(body, dict) or set(body) != {"review", "accept", "findings", "observations"}:
        raise ValueError("expected one scoped review object")
    findings, observations = body["findings"], body["observations"]
    if isinstance(observations, list):
        # A fourth observation is the reviewer being wordy, not being wrong: an
        # observation is non-blocking by construction, it rejects nothing and it
        # never reaches a builder. Refusing the verdict over one threw away a
        # whole paid build, and it could not be retried out of — the same diff
        # draws the same four observations every time. One card in a live
        # campaign was refused twice in a row on it (2026-09-18). The extras are
        # dropped here; the whole reply is on disk as the `diff-review-answer`
        # artifact, so nothing a person can read is lost. The findings cap is a
        # different thing and stays: those block, and three is the budget the
        # prompt declares.
        observations = body["observations"] = observations[:OBSERVATIONS]
    if (body["review"] not in ("ACCEPT", "REJECT") or type(body["accept"]) is not bool
            or body["accept"] != (body["review"] == "ACCEPT")
            or not isinstance(findings, list) or len(findings) > 3
            or not isinstance(observations, list)
            or not all(_text(one) for one in observations)
            or bool(findings) == body["accept"]):
        raise ValueError("inconsistent verdict or finding lists")
    for one in findings:
        if (not isinstance(one, dict)
                or set(one) != {"diff_line", "requirement", "problem", "evidence"}
                or type(one["diff_line"]) is not int or one["diff_line"] < 1
                or not isinstance(one["requirement"], str)
                or one["requirement"] not in REQUIREMENTS
                or not _text(one["problem"]) or not _text(one["evidence"])):
            raise ValueError("a blocker needs a changed line, requirement, problem and evidence")
    return body


def numbered(diff: str) -> str:
    """Render the complete diff using the anchor reader's one-based line numbers."""
    return "".join(f"{number}: {line}" for number, line in
                   enumerate(diff.splitlines(keepends=True), 1))


def changed_lines(diff: str) -> set[int]:
    """Number actual Git changes: hunk lines and explicit metadata/binary markers."""
    changed: set[int] = set()
    old = new = 0
    metadata = False
    for number, line in enumerate(diff.splitlines(), 1):
        hunk = re.fullmatch(r"@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@.*", line)
        if line.startswith("diff --git "):
            metadata, old, new = True, 0, 0
        elif metadata and re.fullmatch(
                r"(?:(?:old|new|new file|deleted file) mode [0-7]{6}"
                r"|(?:rename|copy) (?:from|to) .+|Binary files .+ differ|GIT binary patch)", line):
            changed.add(number)
        elif hunk:
            metadata = False
            old, new = (int(count) if count is not None else 1 for count in hunk.groups())
        elif line.startswith("-") and old:
            changed.add(number)
            old -= 1
        elif line.startswith("+") and new:
            changed.add(number)
            new -= 1
        elif line.startswith(" ") and old and new:
            old -= 1
            new -= 1
        elif not line.startswith("\\ No newline at end of file"):
            old = new = 0
    return changed


def validate(text: str, diff: str) -> dict:
    body = read(text)
    changed = changed_lines(diff)
    if any(one["diff_line"] not in changed for one in body["findings"]):
        raise ValueError("a blocking finding must name an actual changed diff line")
    return body


def summary(body: dict) -> str:
    return "\n".join(f"Diff line {one['diff_line']} ({one['requirement']}): "
                     f"{one['problem']} — {one['evidence']}" for one in body["findings"])
