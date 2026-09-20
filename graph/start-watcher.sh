#!/bin/bash
# The primary is started with this script: cd to the repository, ensure
# WATCHER.session names this session's id (heartbeat.sh's Stop hook matches
# on it — never an env var, which a child claude process would inherit),
# then run WATCHER itself on the personal account (WATCHER_CONFIG_DIR
# overrides it, the same expression alert-watcher.sh's own WATCHER route
# uses). An existing WATCHER.session is left exactly as it is, but the
# session it names IS resumed here (--resume, which reuses the id — see
# `claude --help`'s --fork-session): passing neither flag would let claude
# mint its OWN new id, and the hook would then never match the file at all.
# It takes no arguments at all: a claude flag that can name another session
# or relay is the capability to override the campaign's identity, not
# something to filter, so none is accepted (CLAUDE.md: delete the
# capability rather than guard it). The relay name is unique per session
# id, never the bare "WATCHER": two sessions (a stale background shell and
# the interactive one) can share that bare name, and alert-watcher.sh must
# bind delivery to exactly this one — recorded in WATCHER.name for it to
# read.
# Usage: start-watcher.sh
#        DRY=1 start-watcher.sh   print the command; start nothing
set -u
[ "$#" -eq 0 ] || { echo "start-watcher.sh takes no arguments: the campaign's WATCHER.session and WATCHER.name own the identity" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/../.." || exit 1
W="$(python3 -c 'import sys; sys.path.insert(0, "'"$HERE"'/lib"); import where; print(where.campaign())' 2>/dev/null)" \
  || { echo "$(date -Is) start-watcher: cannot resolve the campaign directory"; exit 1; }
mkdir -p "$W"
if [ -s "$W/WATCHER.session" ]; then
  RESUME=1
  SID="$(cat "$W/WATCHER.session")"
  EXTRA=(--resume "$SID")
else
  RESUME=0
  SID="$(uuidgen)"
  EXTRA=(--session-id "$SID")
fi
NAME="WATCHER-${SID:0:8}"
# The watcher runs on whichever account WATCHER_CONFIG_DIR names; with none
# named it runs on the default account, because only this machine knows where
# a second account's configuration lives.
if [ -n "${WATCHER_CONFIG_DIR:-}" ]; then
  ACCOUNT=(CLAUDE_CONFIG_DIR="$WATCHER_CONFIG_DIR")
else
  ACCOUNT=(-u CLAUDE_CONFIG_DIR)
fi
CMD=(env "${ACCOUNT[@]}" claude --remote-control "$NAME" "${EXTRA[@]}")
if [ "${DRY:-}" = "1" ]; then
  printf '%q ' "${CMD[@]}"; echo
  exit 0
fi
[ "$RESUME" = 0 ] && printf '%s' "$SID" > "$W/WATCHER.session"
printf '%s' "$NAME" > "$W/WATCHER.name"
exec "${CMD[@]}"
