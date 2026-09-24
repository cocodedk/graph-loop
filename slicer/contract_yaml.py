"""One repair for unquoted colons, and the original line when YAML still fails."""

from __future__ import annotations

import re

import yaml

FIELD = re.compile(r'^(?P<prefix>\s*(?:(?:-\s+)?(?P<key>[A-Za-z_][\w-]*):[ \t]+|-[ \t]+))'
                   r'(?P<value>\S.*)$')


def quote_plain_values(text: str) -> str:
    lines = []
    block_indent = None
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        indent = len(body) - len(body.lstrip())
        if block_indent is not None:
            if not body.strip() or indent > block_indent:
                lines.append(line)
                continue
            block_indent = None
        field = FIELD.match(body)
        if field:
            value = field["value"]
            if value.startswith(("|", ">")):
                # A gate's literal shell lines are not YAML mapping fields.
                block_indent = field.start("key") if field["key"] else indent
            elif not value.startswith(('"', "'", "[", "{")) and \
                    (": " in value or value.rstrip().endswith(":")):
                quoted = value.replace("\\", "\\\\").replace('"', '\\"')
                line = f'{field["prefix"]}"{quoted}"{line[len(body):]}'
        lines.append(line)
    return "".join(lines)


def yaml_refusal(text: str, error: yaml.YAMLError) -> ValueError:
    lines = text.splitlines()
    for attr in ("problem_mark", "context_mark"):
        mark = getattr(error, attr, None)
        if mark is not None and 0 <= mark.line < len(lines):
            return ValueError(f"the answer is not YAML: {error}\n"
                              f"offending line {mark.line + 1}:\n{lines[mark.line]}")
    return ValueError(f"the answer is not YAML: {error}")
