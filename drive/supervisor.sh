#!/bin/bash
# Keep the campaign running across the weekend: restart the driver if it dies,
# snapshot the report on every driver exit, check red flags every 15 minutes, and stop the moment the stop flag appears.
# Usage: nohup bash drive/supervisor.sh > /dev/null 2>&1 &
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# The campaign the DRIVER will use, asked of the loop itself: deriving it from
# this script's own path meant that with DRIVE_REPO set the supervisor watched
# one campaign's stop flag while the driver worked in another.
W="$(python3 -c 'import sys; sys.path.insert(0, "'"$HERE"'/lib"); import where; print(where.campaign())')" \
  || { echo "cannot ask the loop where its campaign is" >&2; exit 1; }
mkdir -p "$W/reports"
# One supervisor per campaign: a second start (a person's second `nohup`, a
# retriggered cron) must never race this one's driver, so it takes the lock
# and exits at once rather than doubling up. -n never blocks; held means gone
# quietly, not a hang a person has to notice and kill.
exec 9>"$W/supervisor.lock"
if ! flock -n 9; then
  echo "$(date -Is) another supervisor already holds $W/supervisor.lock — exiting" >&2
  exit 0
fi
# The one supervisor of THIS campaign, named by pid: the board asks whether that
# pid is alive and still a supervisor, because a matching name on the process
# list answers for any campaign's and campaign B's live one kept campaign A's
# dead board green (astra round 4, finding 15). Written after the lock, so only
# the supervisor that won it is the one the campaign names.
printf '%s' "$$" > "$W/supervisor.pid"
# A stand-down nobody could be told about outlives the supervisor that wrote
# it: the file stays until a delivery is proven (alert-watcher.sh removes it),
# every `watch.sh --check` carries it meanwhile, and this start says it again
# at once rather than leaving it to a ticker whose first check is 15 minutes
# away — that silent quarter of an hour is the defect this answers.
if [ -s "$W/stand-down.txt" ]; then
  echo "$(date -Is) a stand-down was never delivered — saying it again" >> "$W/supervisor.log"
  bash "$HERE/alert-watcher.sh" "$W" "$W/stand-down.txt" >> "$W/supervisor.log" 2>&1
fi
fast_failures=0
# Everything a stand-down is, in one place, because there are two ways in: five
# immediate driver deaths, and a disk about to fill. It writes the notice under
# its lock (lib/notice.py) saying which run wrote it — two stand-downs say the
# same words otherwise, and a delivery of the older board took away the newer
# notice unread —, hands it to the messenger synchronously (a background send
# dies with the trap below), then stays up in notice-only mode: no driver, one
# retry every ten minutes, until a delivery is proved (alert-watcher.sh removes
# the file under the same lock) or a stop is asked for. The exit is non-zero: a
# loop that gave up is a failure.
stand_down() {   # $1 = what happened and what to do; $2 = the log's last word
  ( flock 8
    printf '  !! the supervisor stood down: %s   (stood down %s, supervisor %s)\n' \
      "$1" "$(date -Is)" "$$" > "$W/stand-down.txt" ) 8>"$W/stand-down.lock"
  bash "$HERE/alert-watcher.sh" "$W" "$W/stand-down.txt" >> "$W/supervisor.log" 2>&1
  while [ -s "$W/stand-down.txt" ] && [ ! -f "$W/stop.flag" ]; do
    sleep 600      # a messenger call is spend: the notice's own cadence, not the
                   # restart backoff's — and the ticker carries the same notice,
                   # so it can be delivered while this sleeps, and an alert with
                   # nothing in it is not a retry (Codex)
    { [ -f "$W/stop.flag" ] || [ ! -s "$W/stand-down.txt" ]; } && break
    bash "$HERE/alert-watcher.sh" "$W" "$W/stand-down.txt" >> "$W/supervisor.log" 2>&1
  done
  # Last, so it stays the log's last word: the board reads that line, and a
  # retry's output standing there would say the supervisor was still at work.
  echo "$(date -Is) $2" >> "$W/supervisor.log"
  exit 1
}
# The board reads this start line: "quick exits counted" says a quick rc 75 is
# counted like any quick exit here, so `restart_grace` must not spare it.
echo "$(date -Is) supervisor started, restart-aware, quick exits counted" >> "$W/supervisor.log"
# The board's red flags, four times an hour, deterministically: a red check
# hands the flags — each stamped with when it was first seen — to the
# messenger (alert-watcher.sh), which tells the WATCHER session or falls
# back to the log and an email. Only a FATAL flag standing 15+ minutes emails
# the owner — the stand-down above, and nothing else (lib/notice.py); an ordinary
# one is the reader's own to decide and never reaches a mailbox. A disk about
# to fill reaches him through that same stand-down, never beside it.
# None of that is a handoff any more, and nothing waits for it: an alert about
# a card is ANSWERED when the decider decides that card, so it leaves the board
# on its own (lib/workspace_alerts.py, resolve_alerts) instead of standing until
# somebody runs `watch.sh --read`. What is still delivered is delivered because
# seeing it matters — the stand-down, the disk, a driver that is not running. The ticker runs in its
# own process group so stand-down kills the whole tree — a sleep or a live
# messenger included — and its stdio is detached: inheriting this script's
# pipes kept every reader waiting on it long after the supervisor exited.
setsid bash -c 'while true; do
    sleep 900
    [ -f "$1/stop.flag" ] && exit 0
    python3 "$2/lib/sweep_trees.py" >> "$1/supervisor.log" 2>&1   # worktrees of settled cards go: /tmp filled once and killed the host
    if ! bash "$2/watch.sh" --check > "$1/last-check.txt" 2>&1; then
      bash "$2/alert-watcher.sh" "$1" "$1/last-check.txt"
    fi
    # A disk about to fill is infrastructure, not a card: the driver ends after
    # its task (never mid-task) and the loop below stands down before it would
    # start another. Not while a notice already stands — that one is being
    # delivered, and nothing is running to stop.
    if python3 "$2/lib/view_pulse.py" && [ ! -s "$1/stand-down.txt" ]; then
      touch "$1/restart.flag"
    fi
    # every tick, green included: a green check prunes the emailed record, so
    # a flag that clears and returns inside one minute is still news
    python3 "$2/lib/stale_flags.py" "$1" "$1/last-check.txt" >> "$1/supervisor.log" 2>&1
  done' tick "$W" "$HERE" </dev/null >/dev/null 2>&1 9>&- &
TICKER=$!
trap 'kill -- -"$TICKER" 2>/dev/null' EXIT
while true; do
  [ -f "$W/stop.flag" ] && { echo "$(date -Is) stop flag: standing down" >> "$W/supervisor.log"; break; }
  # The disk the worktrees live on, read the one way the board reads it — and
  # said in its words, not a copy of them (lib/view_pulse.py). A full disk
  # killed every process on this host on 2026-09-03, so no driver is started on
  # it: the same stand-down as a dead loop, which is the one route a person is
  # told through (lib/notice.py, astra round 4, finding 16).
  if disk="$(python3 "$HERE/lib/view_pulse.py")"; then
    stand_down "${disk#  }. No driver is started until it is clear; then start this again: bash drive/supervisor.sh" \
               "a disk about to fill: standing down for a person"
  fi
  # The plan phase, before every driver. The two phases never overlap and the
  # driver writes no cards, so a card the build phase parked has exactly one
  # next actor: `plan`, which re-slices the walls, drops what the loop itself
  # held and requeues what the machine broke (lib/plan_phase.py). Nothing but a
  # person ever ran it, so a parked card stayed parked, every driver after it
  # stood down over the same queue, and five of those quick exits emailed
  # somebody that the driver had died.
  # Its exit code is not this loop's to act on: 78 says the graph still has a
  # gap, and the cards that ARE planned are still worth building. What ends the
  # campaign is the driver's own ending, below.
  echo "$(date -Is) planning" >> "$W/supervisor.log"
  python3 "$HERE/drive-goal.py" plan >> "$W/run.log" 2>&1
  planned=$?    # read BEFORE the line below: `$(date -Is)` expands first and is
                # itself a command, so `rc=$?` there reported the date's 0 every time
  echo "$(date -Is) plan phase exited rc=$planned" >> "$W/supervisor.log"
  # A person can stop during a plan phase, which runs for as long as the slicer
  # takes: checked here, no driver is started on a campaign already asked to stop.
  [ -f "$W/stop.flag" ] && { echo "$(date -Is) stop flag after planning" >> "$W/supervisor.log"; break; }
  echo "$(date -Is) starting the driver" >> "$W/supervisor.log"
  started=$(date +%s)
  python3 "$HERE/drive-goal.py" run --idle-seconds 300 >> "$W/run.log" 2>&1
  code=$?; ran=$(( $(date +%s) - started ))
  echo "$(date -Is) driver exited rc=$code after ${ran}s" >> "$W/supervisor.log"
  python3 "$HERE/drive-goal.py" report > "$W/reports/report-$(date +%Y%m%d-%H%M).txt" 2>&1
  [ -f "$W/stop.flag" ] && { echo "$(date -Is) stop flag after exit" >> "$W/supervisor.log"; break; }
  # rc 0 means the backlog is worked out (a stop was caught above): completion
  # is neither a crash nor a request for a person.
  if [ "$code" -eq 0 ]; then
    echo "$(date -Is) driver finished (rc=0): nothing left to run — standing down" >> "$W/supervisor.log"
    break
  fi
  # rc 78 is the other deliberate ending: the source gap was decided against and
  # the campaign ended with its gaps recorded (lib/source_gap.py). Read BEFORE
  # the quick-exit counter, because this exit is quick and is not a death: no
  # restart, no messenger, no mail — the log line is the whole of it, and it says
  # "standing down" so the board reads it as the rc 0 ending it resembles.
  if [ "$code" -eq 78 ]; then
    echo "$(date -Is) driver ended with recorded gaps (rc=78): the sources owe work nobody can plan — standing down" >> "$W/supervisor.log"
    break
  fi
  # A driver that dies at once is broken, not busy — rc 75 included: an exit
  # under 30 seconds is counted, whatever the code, because restarting a driver
  # that keeps dying that fast is invisible churn. The count resets only after
  # a run of 30 seconds or more.
  if [ "$ran" -lt 30 ]; then
    fast_failures=$(( fast_failures + 1 ))
    if [ "$fast_failures" -ge 5 ]; then
      # Nothing is left to notice this: the ticker dies with this script and its
      # first check is 15 minutes away, so five quick deaths ended the loop in
      # silence after about ten. Notice-only mode (stand_down above) is why the
      # supervisor stays up instead of exiting on the first failed delivery,
      # which killed the ticker that owed the retry (astra round 3, finding 16).
      stand_down "the driver died five times in a row, so nothing is running. Read supervisor.log, fix what killed the driver, then start it again: bash drive/supervisor.sh" \
                 "five immediate failures: standing down for a person"
    fi
    sleep $(( 60 * fast_failures ))
  else
    fast_failures=0
    sleep 60
  fi
done
