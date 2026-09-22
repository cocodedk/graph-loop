"""Fresh JUnit failures, appended to the console evidence without hiding it."""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET

from issue_scrub import scrub

HEADING = "\n\nJUnit failures:\n"
LIMIT = 2000
CASES = 20


def excerpt(text: str, *, tail: bool = True) -> str:
    """Keep the existing console window AND the already bounded XML digest.

    Reasons and artifacts are plain text throughout the loop; their heading
    marks the digest so later readers do not cut it or the console away.
    """
    console, heading, digest = text.partition(HEADING)
    return (console[-LIMIT:] if tail else console[:LIMIT]) + heading + digest


def junit_failures(cwd: str, started: int) -> str:
    """Newest reports first, only mtimes at or after this gate's start (ns)."""
    root = pathlib.Path(cwd).resolve()
    reports = []
    for path in root.glob("**/build/test-results/**/TEST-*.xml"):
        try:
            if not path.resolve().is_relative_to(root) or not path.is_file():
                continue
            mtime = path.stat().st_mtime_ns
            if mtime >= started:
                reports.append((mtime, path))
        except OSError:
            continue  # a report removed while looking is not evidence
    lines, total = [], 0
    for _, path in sorted(reports, key=lambda item: (-item[0], item[1])):
        try:
            suite = ET.parse(path)
        except (OSError, ET.ParseError):
            continue  # partial/unreadable XML must never change the gate's verdict
        for case in suite.iterfind(".//{*}testcase"):
            failure = case.find("{*}failure")
            if failure is None:
                failure = case.find("{*}error")
            if failure is None:
                continue
            total += 1
            if len(lines) < CASES:
                message = (failure.get("message") or failure.text or "").splitlines()
                line = (f"- {case.get('classname', '')}.{case.get('name', '')}: "
                        f"{failure.get('type', '')}: {message[0] if message else ''}")
                lines.append(scrub(line, set()))
    if not total:
        return ""
    while True:
        more = f"\n… and {total - len(lines)} more" if total > len(lines) else ""
        digest = HEADING + "\n".join(lines) + more
        if len(digest) <= LIMIT:
            return digest
        lines.pop()
