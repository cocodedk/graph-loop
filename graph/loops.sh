#!/bin/bash
# A live screen to switch between lean loops. All the reading lives in loops.py (--screen, --path);
# this file only clears the screen, prints, waits for a key and prints again.
#   bash graph/loops.sh [project-folder]      keep looking, every LOOPS_REFRESH seconds (15)
#   bash graph/loops.sh -1 [project-folder]   one look and stop
#   keys: 1-9 switch loop · f filter · q quit; any other key refreshes. Ctrl-C stops it.
# LOOPS_CMD is the command that answers (`python3 graph/loops.py` when unset); the tests fake it.
REFRESH="${LOOPS_REFRESH:-15}"
# An array keeps the path of loops.py whole when it has spaces; LOOPS_CMD splits into words.
if [ -n "${LOOPS_CMD:-}" ]; then read -r -a CMD <<< "$LOOPS_CMD"; else CMD=(python3 "$(cd "$(dirname "$0")" && pwd)/loops.py"); fi
ONCE=""
[ "${1:-}" = "-1" ] && { ONCE="--once"; shift; }
folder="${1:-}"
only=""

# The commands read no keys: standard input belongs to the person, so a key pressed while one runs
# waits in the input until the next read.
rows=""   # the terminal's height, read before each live refresh; a single look never passes it
screen() {
  "${CMD[@]}" --screen ${folder:+"$folder"} ${only:+--only "$only"} --refresh "$REFRESH" ${rows:+--rows "$rows"} $ONCE 2>&1 </dev/null
}

if [ -n "$ONCE" ]; then
  screen
  exit $?
fi

stop() { echo "stopped watching."; exit 0; }
trap 'echo; stop' INT
while true; do
  # here, not inside $(screen): tput finds the height from the terminal only while its error output still is one;
  # with no terminal, or one tput does not know (TERM unset), it is not asked, so it prints no error
  rows=""
  if command -v tput >/dev/null; then
    if [ -t 2 ]; then tput longname >/dev/null 2>&1 && rows="$(tput lines)"; else rows="$(tput lines 2>/dev/null)"; fi
  fi
  case "$rows" in *[!0-9]*) rows="" ;; esac
  text="$(screen)"  # build the whole screen first, so the person never sees an empty one
  clear 2>/dev/null || true
  printf '%s\n' "$text"
  IFS= read -rsn1 -t "$REFRESH" key
  [ $? -eq 1 ] && stop   # end of input: as if q was pressed (a timeout is above 128)
  case "$key" in
    [1-9]) # ponytail: one key reaches loops 1-9, a prompt for a number later
           # the folder a fresh --path gives now: the numbers may have moved since the last screen
           path="$("${CMD[@]}" --path "$key" 2>/dev/null </dev/null)" && [ -n "$path" ] && folder="$path" ;;
    f) case "$only" in
         "") only=built ;; built) only=open ;; open) only=attention ;; *) only="" ;;
       esac ;;
    q) stop ;;
  esac
done
