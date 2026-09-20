#!/bin/bash
# Stop hook: touches this session's heartbeat file so alert-watcher.sh
# knows whether WATCHER (or its stand-in WATCHER-STANDIN) is actually
# watching. Fires whenever a turn completes, cross-session SendMessage
# relays included, so a real reply counts with no separate "I'm watching"
# call needed — and a request that fails (a usage limit, say) never
# completes a turn, so the heartbeat then correctly goes stale.
#
# Which heartbeat (if any) gets touched is decided ONLY by the hook's own
# stdin session_id matching a recorded .session file — never an environment
# variable. An env var (WATCHER_ROLE used to be one) is inherited by every
# child claude process — the supervisor's messenger, every builder — and
# this same hook runs for them too, so a builder's own Stop would falsely
# refresh the watcher's heartbeat. start-watcher.sh and handoff-standin.sh each
# pass their own --session-id and record it in WATCHER.session /
# WATCHER-STANDIN.session before starting, so the id here can only ever match
# the one real session it names.
#
# Never blocks anything: any failure here (no campaign yet, an unwritable
# dir, unparsable stdin) is silently a no-op.
# Usage: wired in .claude/settings.json as a Stop hook.
set -u
# The messenger's own claude -p sub-call fires this hook too (same repo,
# same hook wiring) — GRAPH_MESSENGER=1 tells it apart from a real wake, or
# a persistently red board would touch a heartbeat every tick forever.
[ -n "${GRAPH_MESSENGER:-}" ] && exit 0
HERE="$(cd "$(dirname "$0")" && pwd)"
W="$(python3 -c 'import sys; sys.path.insert(0, "'"$HERE"'/lib"); import where; print(where.campaign())' 2>/dev/null)" || exit 0

SESSION_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)
[ -z "$SESSION_ID" ] && exit 0

if [ -f "$W/WATCHER.session" ] && [ "$SESSION_ID" = "$(cat "$W/WATCHER.session")" ]; then
  touch "$W/WATCHER.heartbeat" 2>/dev/null
elif [ -f "$W/WATCHER-STANDIN.session" ] && [ "$SESSION_ID" = "$(cat "$W/WATCHER-STANDIN.session")" ]; then
  touch "$W/WATCHER-STANDIN.heartbeat" 2>/dev/null
fi
exit 0
