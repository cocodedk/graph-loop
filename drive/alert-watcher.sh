#!/bin/bash
# The board went red and nobody may be watching: a small Claude messenger
# (Opus 5, effort low) tells the WATCHER session — or, when WATCHER's own
# heartbeat has gone stale, its stand-in WATCHER-STANDIN (handoff-standin.sh starts
# it if it is not already up, and the send is retried once). When nobody can
# be reached, this script warns mechanically: the supervisor log, and an
# email (lib/alert_email.py — fill smtp.env beside it; until then it logs
# what it could not do). Deterministic except the messenger call(s).
# Delivery is proven by lib/alert_proof.py reading the call record itself,
# never by the model's own prose — the real shape it matches (two sessions
# can share one name; ListAgents then answers e.g. "WATCHER [b362c3]") is
# documented there, read from a live call record,
# scratchpad/drive-campaigns/current/messenger-20260903-081817-2008870.jsonl.
# Usage: alert-watcher.sh <campaign-dir> <check-output-file>
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
W=$1; CHECK=$2
# the WHOLE file (a byte cap once dropped every warning after the first few),
# read ONCE into this run's own snapshot. The check file is not this script's:
# the supervisor's tick waits for this script, but anyone else can rewrite it
# while a messenger call takes five minutes. Prompt, mail and the comparison
# that clears the fatal notice read these bytes; the snapshot goes on the way out.
FLAGS="$(cat "$CHECK")"; [ -n "$FLAGS" ] || { echo "$(date -Is) alert-watcher: nothing to read in $CHECK — nothing sent" >> "$W/supervisor.log"; exit 1; }
# A snapshot nobody could write is not a payload: unchecked, a run that could
# make none mailed an empty body. The trap is armed before the file exists.
PAYLOAD="$(mktemp)" || { echo "$(date -Is) alert-watcher: no temporary file for the payload — nothing sent" >> "$W/supervisor.log"; exit 1; }
trap 'rm -f "$PAYLOAD"' EXIT
LAST="$W/watcher-alert.last"
# Dedupe on the flags' stable identity, not their rendered text: a minute
# counter that ticks ('for 25 minutes' -> 'for 40') is the same standing red,
# while a new task id is news. TICKING (lib/view_stamps.py) is the one rule.
IDENTITY=$(printf '%s' "$FLAGS" | python3 "$HERE/lib/view_stamps.py")

# WATCHER touches its own heartbeat on every wake. Younger than 30 minutes:
# it is watching, target it as always. A MISSING file (every test rig, and
# any campaign before WATCHER's first wake) is not evidence of staleness —
# only an existing, old file is — so it defaults to WATCHER too; only a
# heartbeat that has actually gone stale on a live campaign moves the
# target to the stand-in. Chosen before the dedupe check below: the target
# is part of what "the same as last time" means, so a heartbeat going stale
# (or recovering) between ticks must resend even flags that did not change.
HB="$W/WATCHER.heartbeat"
TARGET=WATCHER
# is_fresh (lib/heartbeat_age.py) is the one definition of "fresh" shared
# with stale_flags.py's escalation hold, so the two can never disagree about
# whether someone is watching this same board.
if [ -f "$HB" ] && ! python3 -c "
import pathlib, sys
sys.path.insert(0, '$HERE/lib')
from heartbeat_age import is_fresh
sys.exit(0 if is_fresh(pathlib.Path('$HB')) else 1)"; then
  TARGET=WATCHER-STANDIN
fi

# A live campaign can have two sessions sharing one bare name (a stale
# background shell and the interactive one), so a bare name alone can never
# bind delivery to the session that owns the heartbeat. Each launcher
# records its own unique relay name in <role>.name (start-watcher.sh writes
# WATCHER.name, handoff-standin.sh writes WATCHER-STANDIN.name); read fresh before
# every send, since handoff-standin.sh may just have written one. Falls back to
# the bare role name only when no file exists yet, for older campaigns.
relay_name() {  # $1 = role (WATCHER or WATCHER-STANDIN)
  local f="$W/$1.name"
  if [ -s "$f" ]; then cat "$f"; else printf '%s' "$1"; fi
}
NAME="$(relay_name "$TARGET")"

# The same standing red to the same target every tick is one message, not
# one per tick — but a target change is news on its own, so it is part of
# the dedupe key, not just the flags' identity. Keyed on the resolved NAME,
# not the bare role: a replacement session (a new .name, same role) is news
# too — the old name's session may no longer be the one watching.
KEY="$NAME:$IDENTITY"
# Two records, not one. `remember` is the MESSENGER's dedupe key, written by a
# proven delivery to either target; the email fallback below is narrower.
# `clear_notice` is the supervisor's fatal stand-down, which stops standing
# when a channel carried its words and stays otherwise: lib/notice.py compares
# it with what went out, under supervisor.sh's lock, so an older, unrelated
# board takes nothing away.
remember() { printf '%s' "$KEY" > "$LAST"; }
clear_notice() { printf '%s' "$FLAGS" | python3 "$HERE/lib/notice.py" "$W" 2>>"$W/supervisor.log"; }
if [ -f "$LAST" ] && [ "$KEY" = "$(cat "$LAST")" ]; then
  echo "$(date -Is) alert-watcher: flags unchanged, not re-sent" >> "$W/supervisor.log"
  exit 0
fi

# Who these flags may be handed to: only a fatal board names the owner (lib/notice.py,
# one reading shared with the 15-minute escalation in stale_flags.py).
WHO="$(printf '%s' "$FLAGS" | python3 "$HERE/lib/notice.py" --audience)"
BODY="The drive campaign's board went red — detected $(date -Is) by the supervisor's deterministic tick.
Act on every warning below THIS TURN. Each line carries the time it was first seen; the older it
is, the less excuse it has to still stand. For each one: find the root cause and fix it now.
$WHO Ignore none of them.
$FLAGS"

# One call record per attempt, kept: an overwritten record cannot be read
# back when an earlier attempt is questioned. Sets RC and PROVEN in this
# shell (no subshell) so the caller can read them straight after.
send_target() {  # $1 = role (decides the account), $2 = exact relay name
                  # (what the relay must find and proven() must match), $3 = record path
  local role="$1" name="$2" record="$3"
  # DRIVE_MESSENGER=1 marks this as the throwaway messenger call, not a real
  # session waking up: it runs in this same repo, so the project's Stop hook
  # (heartbeat.sh) fires for it too regardless of which account it
  # authenticates as — a persistently red board would otherwise touch a
  # heartbeat every tick forever and stale routing could never trigger.
  # heartbeat.sh reads this and no-ops.
  # Peer discovery (ListAgents) is scoped to the config dir a session runs
  # under, so the messenger authenticates as whichever account can see the
  # target: the account WATCHER_CONFIG_DIR names — set explicitly, never
  # just inherited, since the supervisor itself may run from either
  # account — and the default account (cleared) for the stand-in, and for
  # the watcher when nothing names a second account.
  if [ "$role" = WATCHER ] && [ -n "${WATCHER_CONFIG_DIR:-}" ]; then
    local config_dir=(CLAUDE_CONFIG_DIR="$WATCHER_CONFIG_DIR")
  else
    local config_dir=(-u CLAUDE_CONFIG_DIR)
  fi
  printf '%s' "Use ListAgents to list reachable sessions. Find the session named exactly $name.
Send it this message with SendMessage, verbatim:
---
$BODY
---
If and only if no session named exactly $name exists, print exactly NO-$name." \
    | env "${config_dir[@]}" DRIVE_MESSENGER=1 timeout 300 claude -p --model claude-opus-5 --effort low \
        --output-format stream-json --verbose \
        --tools "ListAgents,SendMessage" \
        --permission-mode default --allowedTools "ListAgents,SendMessage" \
        --disallowedTools "Bash,Edit,Write,Agent,WebFetch,WebSearch" \
        > "$record" 2>>"$W/supervisor.log"
  RC=$?
  PROVEN=$(RECORD="$record" BODY="$BODY" NAME="$name" python3 -c "
import os, sys
sys.path.insert(0, '$HERE/lib')
from alert_proof import proven
print('yes' if proven(os.environ['RECORD'], os.environ['BODY'], os.environ['NAME']) else 'no')" \
    2>>"$W/supervisor.log")
}

RECORD="$W/messenger-$(date +%Y%m%d-%H%M%S)-$$.jsonl"
send_target "$TARGET" "$NAME" "$RECORD"

# WATCHER-STANDIN may simply not be up yet: start it (handoff-standin.sh is
# idempotent — a no-op if it is already running) and give the send one
# retry before falling back to email. The WATCHER path stays as today: no
# stand-in is started on its account, a failed send there goes straight to
# the warning below. HANDOFF_CAW overrides which script runs — tests use it
# to swap in a bare-exit stub, so this suite never has to start a real tmux.
if [ "$TARGET" = WATCHER-STANDIN ] && { [ "$RC" -ne 0 ] || [ "$PROVEN" != "yes" ]; }; then
  echo "$(date -Is) alert-watcher: WATCHER-STANDIN not reached, starting the stand-in" >> "$W/supervisor.log"
  if bash "${HANDOFF_CAW:-$HERE/handoff-standin.sh}" >> "$W/supervisor.log" 2>&1; then
    NAME="$(relay_name "$TARGET")"    # handoff-standin.sh may have just written a new one
    KEY="$NAME:$IDENTITY"             # keep $LAST in sync with the name actually used below
    RECORD="$W/messenger-$(date +%Y%m%d-%H%M%S)-$$-retry.jsonl"
    send_target "$TARGET" "$NAME" "$RECORD"
  fi
fi

if [ "$RC" -eq 0 ] && [ "$PROVEN" = "yes" ]; then
  remember
  clear_notice
  echo "$(date -Is) alert-watcher: red flags delivered to $TARGET (send proven by ${RECORD##*/})" >> "$W/supervisor.log"
  exit 0
fi

# Nobody could be reached (or the messenger died): warn loudly, mechanically.
# The MESSENGER'S OWN dedupe record ($LAST) is written by a PROVEN delivery and
# by nothing else — the mail below carries the fatal lines, not the board, so it
# never stands in for a send: a flag that reached nobody is retried on the next
# tick, whatever target was tried and whatever went out by mail.
# The EMAIL keeps its own record ($EMAIL_LAST), or an unreachable messenger
# would re-mail the same standing state every tick. It is keyed on $MAILING —
# the fatal payload with its counters blanked, the mail's own bytes — never on
# the board or the target: "the same red" is what the mail said, so an ordinary
# flag changing beside it is not news, nor is a switch of target.
WHY="the messenger could not prove a delivery to $TARGET (rc=$RC; the call record is ${RECORD##*/})"
echo "$(date -Is) alert-watcher WARNING: $WHY" >> "$W/supervisor.log"
# A mail is for what only a person can clear (lib/notice.py). The whole board
# turned every ordinary warning into an escalation as soon as a messenger could
# not be reached, so the payload is the fatal lines alone — none, no mail.
printf '%s\n' "$FLAGS" | python3 "$HERE/lib/notice.py" --mail > "$PAYLOAD" \
  || { echo "$(date -Is) alert-watcher: nothing here is a person's to clear — not emailed, and the messenger is tried again next tick" >> "$W/supervisor.log"; exit 1; }
# and the mail's dedupe is the mail's OWN bytes, blanked the same way: keyed on
# the whole board, an ordinary flag changing beside the fatal one sent the
# identical mail again (Codex).
EMAIL_LAST="$W/email.last"; MAILING=$(python3 "$HERE/lib/view_stamps.py" < "$PAYLOAD")
if [ -f "$EMAIL_LAST" ] && [ "$MAILING" = "$(cat "$EMAIL_LAST")" ]; then
  echo "$(date -Is) alert-watcher: already emailed for this standing state — not re-sent" >> "$W/supervisor.log"
  exit 1
fi
if python3 "$HERE/lib/alert_email.py" "$WHY" "$PAYLOAD" >> "$W/supervisor.log" 2>&1; then
  printf '%s' "$MAILING" > "$EMAIL_LAST"
  # The mail went out: the notice it carried stops standing, whichever target
  # the messenger had been trying. The messenger's own record is NOT written
  # here — this mail carried the fatal lines, not the board, and the warnings
  # beside them are still owed to a session that comes back (Codex).
  clear_notice
  exit 0
fi
echo "$(date -Is) alert-watcher: nobody was reached — retrying next tick" >> "$W/supervisor.log"
exit 1
