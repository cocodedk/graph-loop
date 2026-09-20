#!/bin/bash
# Starts WATCHER's stand-in: a claude --remote-control session on the work
# account (env -u CLAUDE_CONFIG_DIR clears any config dir this run inherited),
# named uniquely per launch (WATCHER-STANDIN-<8 hex of its session id>, because
# two sessions can share the bare name and alert-watcher.sh must bind
# delivery to exactly this one), in a tmux (or screen) session named
# watcher-standin-<8 hex of the campaign directory> so the owner can follow it from
# his phone (`tmux ls`). The campaign is IN that name because a bare shared
# one let one campaign's handoff kill another campaign's live session.
# Idempotent: an already-running session is confirmed and nothing else happens.
# alert-watcher.sh calls this when WATCHER's beat is stale and the first send
# to WATCHER-STANDIN went unproven; that send is then retried once.
# Usage: handoff-standin.sh          start it, or confirm it is already running
#        DRY=1 handoff-standin.sh    print the command it would run; start nothing
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
W="$(python3 -c 'import sys; sys.path.insert(0, "'"$HERE"'/lib"); import where; print(where.campaign())' 2>/dev/null)" \
  || { echo "$(date -Is) handoff-standin: cannot resolve the campaign directory"; exit 1; }
# The one place the session name is derived, campaign and all: DRY prints it,
# every tmux call below addresses it, and no other script names it.
SESSION="watcher-standin-$(printf '%s' "$W" | md5sum | cut -c1-8)"
# A fresh id every run, recorded in WATCHER-STANDIN.session (and the relay name
# it derives, in WATCHER-STANDIN.name) only when this run really starts a session
# below. heartbeat.sh's Stop hook matches on the id and never on an env var —
# a child claude process inherits one of those too, the bug this replaced.
SID="$(uuidgen)"
NAME="WATCHER-STANDIN-${SID:0:8}"
# THIS campaign's branch, asked of the loop itself (campaign_of.branch_of, the
# reading the driver builds its keeper with), so the stand-in is never pointed
# at a branch its own driver is not using: a brief naming a fixed branch handed
# campaign B campaign A's merges, pushes and restarts (astra round 4, finding
# 14). The session carries campaign and branch too, so every tool it runs —
# heartbeat.sh, which beats for it — resolves the same campaign.
BRANCH="$(python3 -c '
import sys
sys.path.insert(0, "'"$HERE"'/lib")
import where
from campaign_of import branch_of
from keep_branch import plain
from workspace import Workspace
print(plain(branch_of(Workspace(where.campaign()))))')"
# An empty answer is a broken helper, never a campaign: brief nobody on it.
[ -n "$BRANCH" ] || { echo "$(date -Is) handoff-standin: cannot read this campaign's branch — no stand-in started"; exit 1; }
CMD="env -u CLAUDE_CONFIG_DIR GRAPH_CAMPAIGN='$W' GRAPH_BRANCH='$BRANCH' claude --remote-control $NAME --session-id $SID --model claude-opus-5 --effort high"

if command -v tmux >/dev/null 2>&1; then
  BACKEND=tmux
elif command -v screen >/dev/null 2>&1; then
  BACKEND=screen
else
  echo "$(date -Is) handoff-standin: neither tmux nor screen is on PATH — cannot start the stand-in"
  exit 3
fi

if [ "${DRY:-}" = "1" ]; then
  case "$BACKEND" in
    tmux) echo "tmux new-session -d -s $SESSION -c $REPO \"$CMD\"" ;;
    *)    echo "screen -dmS $SESSION bash -c \"cd '$REPO' && $CMD\"" ;;
  esac
  exit 0
fi

# The brief is this campaign's: STAND-IN.md's placeholders filled in here, and
# both backends send the rendered copy.
BRIEF="$(mktemp)" || { echo "$(date -Is) handoff-standin: no temporary file for the brief — nothing started"; exit 1; }
trap 'rm -f "$BRIEF"' EXIT
sed -e "s|{{CAMPAIGN}}|$W|g" -e "s|{{BRANCH}}|$BRANCH|g" "$HERE/STAND-IN.md" > "$BRIEF"

# One launch or replacement per campaign at a time. Two ticks that both found
# the session missing both started one, and the loser's cleanup killed the
# winner's live session (astra round 3, finding 17). `-n` never blocks: a
# handoff already running IS the one this call wanted, so this one leaves.
exec 7>"$W/handoff.lock"
if ! flock -n 7; then
  echo "$(date -Is) handoff-standin: another handoff for this campaign is running — leaving it to that one"
  exit 1
fi

# A launch or brief step that fails AFTER the session started must not leave a
# stale record or a running-but-unbriefed session: a later tick's has-session
# (or screen -list) check would read it as "already up" and skip retrying for
# ever. Nothing to kill before the session exists.
fail() {  # $1 = one-line reason
  echo "$(date -Is) handoff-standin: $1"
  # Only the session THIS run started: the identity file names it, and a
  # launch that took over since owns both the session and the record.
  if [ "$(cat "$W/WATCHER-STANDIN.session" 2>/dev/null)" = "$SID" ]; then
    case "$BACKEND" in
      tmux) tmux kill-session -t "$SESSION" 2>/dev/null ;;
      *)    screen -S "$SESSION" -X quit 2>/dev/null ;;
    esac
    rm -f "$W/WATCHER-STANDIN.session" "$W/WATCHER-STANDIN.name"
  fi
  exit 1
}

# "Already up" is the session WE recorded, still answering; one merely existing
# under this name proves neither. On 2026-09-03 a send to WATCHER-STANDIN failed,
# this script said "already up", and the same tick's retry failed again.
# heartbeat.sh beats only for the id in WATCHER-STANDIN.session, and is_fresh
# (lib/heartbeat_age.py) is the one definition of fresh.
answering() {   # has the session we recorded completed a turn recently?
  python3 -c "
import pathlib, sys
sys.path.insert(0, '$HERE/lib')
from heartbeat_age import is_fresh
sys.exit(0 if is_fresh(pathlib.Path('$W/WATCHER-STANDIN.heartbeat')) else 1)"
}
ours() {  # $1 = the command line the running session was started with
  [ -s "$W/WATCHER-STANDIN.session" ] || return 1
  case "$1" in *"--session-id $(cat "$W/WATCHER-STANDIN.session")"*) return 0 ;; esac
  return 1
}
record() {  # this launch owns the identity from here on
  # A beat belongs to the session that made it: left in place, the replaced
  # session's beat answers for the one we start and the next call says "already
  # up" about a session that never answered. Cleared BEFORE the id is recorded,
  # so a crash between the two lines leaves no beat outliving its session.
  rm -f "$W/WATCHER-STANDIN.heartbeat"
  printf '%s' "$SID" > "$W/WATCHER-STANDIN.session"
  printf '%s' "$NAME" > "$W/WATCHER-STANDIN.name"
}
# ponytail: a stand-in whose FIRST turn outlives the freshness window is replaced rather than waited for. Upgrade: a launch's own grace period.
# A session under this name that `ours` cannot account for is somebody else's —
# a launch whose record was lost, a person's own terminal — and killing it is
# not this run's to do (round-4 finding 13): said on stderr and in the
# supervisor's record, nothing started or removed.
conflict() {  # $1 = what was found under our name
  echo "$(date -Is) handoff_conflict: $1 — left running, no stand-in started" \
    | tee -a "$W/supervisor.log" >&2
  exit 2
}

if [ "$BACKEND" = tmux ]; then
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    ours "$(tmux list-panes -t "$SESSION" -F '#{pane_start_command}' 2>/dev/null)" \
      || conflict "$SESSION was started with an id this campaign never recorded"
    if answering; then
      echo "$(date -Is) handoff-standin: $SESSION is already up"
      exit 0
    fi
    echo "$(date -Is) handoff-standin: $SESSION is ours and has not answered — replacing it"
    tmux kill-session -t "$SESSION" 2>/dev/null
  fi
  record
  # 7>&- 9>&-: the session outlives this script, and a tmux client with no
  # server forks one that keeps every open descriptor for as long as the
  # session lives. Inherited, the handoff lock (7) would be held by the
  # stand-in itself and every later handoff would say "another handoff is
  # running" for ever; 9 is the supervisor's own lock, riding in from its tick.
  tmux new-session -d -s "$SESSION" -c "$REPO" "$CMD" 7>&- 9>&- \
    || fail "tmux new-session failed"
  # Bounded wait for the session to render before pasting into it: two
  # identical captures in a row, or thirty seconds, whichever comes first —
  # cheaper than knowing the exact banner text. A session that is gone once
  # the wait ends never rendered a prompt to paste into.
  prev=""; n=0
  while [ "$n" -lt 15 ]; do
    cur="$(tmux capture-pane -pt "$SESSION" 2>/dev/null)"
    [ -n "$cur" ] && [ "$cur" = "$prev" ] && break
    prev="$cur"; sleep 2; n=$((n + 1))
  done
  tmux has-session -t "$SESSION" 2>/dev/null || fail "$SESSION exited before it settled"
  # A pasted buffer, not typed keys: the brief is many lines, and typing them
  # would fire Enter — and submit — after every one. tmux wraps a paste-buffer
  # in bracketed paste when the app asks for it, so a pasted newline stays a
  # newline; send-keys Enter, after the paste, is what submits it.
  tmux load-buffer -b "$SESSION-brief" "$BRIEF" \
    && tmux paste-buffer -p -b "$SESSION-brief" -t "$SESSION" \
    || fail "pasting the standing brief failed"
  tmux send-keys -t "$SESSION" Enter || fail "submitting the standing brief failed"
else
  if screen -list 2>/dev/null | grep -q "\.${SESSION}[[:space:]]"; then
    # ponytail: screen cannot report a session's start command, so ours here is
    # only "this campaign recorded an id". Upgrade: the tmux check above.
    [ -s "$W/WATCHER-STANDIN.session" ] \
      || conflict "$SESSION is running and this campaign recorded no session of its own"
    if answering; then
      echo "$(date -Is) handoff-standin: $SESSION is already up"
      exit 0
    fi
    echo "$(date -Is) handoff-standin: $SESSION is ours and has not answered — replacing it"
    screen -S "$SESSION" -X quit 2>/dev/null
  fi
  record
  screen -dmS "$SESSION" bash -c "cd '$REPO' && $CMD" 7>&- 9>&-   # as above: it outlives this
  n=0
  while [ "$n" -lt 15 ] && ! screen -list 2>/dev/null | grep -q "\.${SESSION}[[:space:]]"; do
    sleep 2; n=$((n + 1))
  done
  screen -list 2>/dev/null | grep -q "\.${SESSION}[[:space:]]" || fail "$SESSION never appeared"
  sleep 2
  # ponytail: screen has no bracketed paste like tmux's paste-buffer -p, so
  # `stuff` types the brief literally and a chat box that submits on Enter may
  # see it in fragments. Upgrade: readbuf/paste registers, if screen goes live.
  screen -S "$SESSION" -X stuff "$(cat "$BRIEF")$(printf '\r')" \
    || fail "sending the standing brief failed"
fi
echo "$(date -Is) handoff-standin: $SESSION started, standing brief sent"
