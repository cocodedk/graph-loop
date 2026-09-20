#!/usr/bin/env bash
# Nothing local travels.
#
# Two halves, because they have different lifetimes.
#
# The shipped half, below, carries only structural patterns — shapes that name
# nobody: a home directory, an agent configuration directory, a commit hash. It
# is tracked, it is published, and it is what CI runs. It contains no literal it
# forbids, so it does not need to exclude itself from its own scan.
#
# The extraction half is a private denylist naming one migration's accounts,
# repository and vocabulary. It never enters this repository. Pass it by path:
#
#     scripts/scrub-check.sh /path/to/denylist        (one extended regex per line)
#
# Scanned: tracked contents, tracked filenames, and the full history. A clean
# working tree proves nothing if the commit before it still names something.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

denylist="${1:-${GRAPH_SCRUB_DENYLIST:-}}"
fail=0

contents() {  # <label> <extended-regex>
  local label="$1" re="$2" hits
  hits=$(git ls-files -z | xargs -0 grep -nIE "$re" 2>/dev/null || true)
  verdict "content: $label" "$hits"
}

filenames() {
  local label="$1" re="$2" hits
  hits=$(git ls-files | grep -E "$re" || true)
  verdict "names:   $label" "$hits"
}

history() {
  local label="$1" re="$2" hits
  hits=$(git log --all -p --format='commit %H' | grep -E "$re" | head -20 || true)
  verdict "history: $label" "$hits"
}

verdict() {
  if [ -n "$2" ]; then
    echo "FAIL: $1"
    echo "$2" | sed 's/^/  /'
    fail=1
  else
    echo "ok:   $1"
  fi
}

# Written so the pattern text cannot match the pattern: a character class
# around the first character of each literal. The check scans itself like any
# other file, and must come up clean.
HOMES='/home/[a-z]|/Users/[a-z]|[$]HOME/|~/[.]claude'
CONFIG='[.]claude-(personal|shared)'
HASH='`[0-9a-f]{7,40}`'
# A loopback address is a machine's own wiring, never a public tool's.
LOCALHOST='127[.]0[.]0[.]1|localhost:[0-9]|0[.]0[.]0[.]0'

contents  "no home directories"          "$HOMES"
contents  "no agent configuration paths" "$CONFIG"
contents  "no bare commit hashes"        "$HASH"
contents  "no loopback addresses"        "$LOCALHOST"
filenames "no local machine config"      '^[.]mcp[.]json$|[.]local([.]md)?$'
filenames "no local paths in filenames"  "$HOMES|$CONFIG"
history   "no home directories"          "$HOMES"
history   "no agent configuration paths" "$CONFIG"

if [ -n "$denylist" ]; then
  if [ ! -f "$denylist" ]; then
    echo "FAIL: denylist '$denylist' does not exist"
    exit 1
  fi
  while IFS= read -r re; do
    [ -z "$re" ] && continue
    case "$re" in \#*) continue ;; esac
    contents  "denylist" "$re"
    filenames "denylist" "$re"
    history   "denylist" "$re"
  done < "$denylist"
else
  echo "note: no extraction denylist given — structural patterns only."
  echo "      Pass one while the extraction is in progress."
fi

if [ "$fail" -ne 0 ]; then
  echo
  echo "The repository names something it must not. Fix the file, not this check."
  exit 1
fi
echo
echo "Nothing local travels."
