"""Whether the messenger actually delivered the alert.

The model's prose is untrusted input: delivery is proven only by the call
record itself (stream-json, one event per line) — a SendMessage tool call
whose `to` names the target session and whose message is the instructed
body, answered by a tool_result whose own payload says success true. A
flags-only or paraphrased message, or a refused send (`{"success": false}`,
carried with no `is_error` flag), proves nothing.

Real shape, read from a live messenger call record
(scratchpad/drive-campaigns/current/messenger-20260903-081817-2008870.jsonl):
`to` came back "WATCHER [b362c3]", not the bare "WATCHER" — ListAgents had
two sessions named WATCHER (a background shell and an interactive one) and
the model disambiguated with the session id it listed them under. An
exact-string match against the bare target name never fires, so every
proven delivery read as unproven and every one emailed the owner besides. `to`
now matches the bare target or the target plus that " [id]" suffix, full
matched against that exact six-hex-digit shape — not any text starting that
way. A record is untrusted input end to end: a tool call's own id, and a
tool_result's correlating id, must both be a non-empty string before they
can prove anything, so a record with a missing or malformed id neither
proves a delivery nor crashes the check.

The same untrusted-input rule applies to every container along the path, not
just the id fields: valid JSON whose `event`, `message`, `input`, or a
tool_result's parsed content is not the object shape expected (a list, a
string, a number) used to crash the read with an AttributeError from a bare
`.get()`. Each container is now isinstance-checked before `.get` is called on
it; a wrong shape skips that line or block and proves nothing, rather than
raising.
"""

from __future__ import annotations

import json
import re


def _names(to: str, target: str) -> bool:
    to = to.strip()
    return to == target or re.fullmatch(re.escape(target) + r" \[[0-9a-f]{6}\]", to) is not None


def proven(record_path: str, body: str, target: str = "WATCHER") -> bool:
    wanted = body.strip()
    sent, ok = set(), False
    with open(record_path, encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            message = event.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                tool_id = block.get("id")
                tool_input = block.get("input")
                if (block.get("type") == "tool_use" and block.get("name") == "SendMessage"
                        and isinstance(tool_id, str) and tool_id
                        and isinstance(tool_input, dict)
                        and _names(str(tool_input.get("to", "")), target)
                        and wanted
                        and str(tool_input.get("message", "")).strip() == wanted):
                    sent.add(tool_id)
                result_id = block.get("tool_use_id")
                if (block.get("type") == "tool_result"
                        and isinstance(result_id, str) and result_id in sent
                        and not block.get("is_error")):
                    result_content = block.get("content")
                    if isinstance(result_content, list):
                        result_content = " ".join(str(part.get("text", "")) for part in result_content
                                                   if isinstance(part, dict))
                    try:
                        parsed = json.loads(str(result_content))
                    except ValueError:
                        continue
                    if isinstance(parsed, dict) and parsed.get("success") is True:
                        ok = True
    return ok
