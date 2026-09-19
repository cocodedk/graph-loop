#!/bin/bash
# The window on the loop. All the reading lives in lib/view.py, one function per
# section; this file only clears the screen and refreshes.
#   bash drive/watch.sh          keep looking, every REFRESH_SECONDS
#   bash drive/watch.sh -1 [-v]   one look and stop
#   bash drive/watch.sh -v        keep looking, and show the last review
#   bash drive/watch.sh --check   only the red flags; exit 1 if there are any
#   bash drive/watch.sh --ledger  when, which card, what came of it
#   bash drive/watch.sh --read    mark the alerts shown now as read; later ones still show
#   Ctrl-C stops it.
REFRESH_SECONDS=15
VIEW="$(cd "$(dirname "$0")" && pwd)/lib/view.py"

for arg in "$@"; do [ "$arg" = "--check" ] && { python3 "$VIEW" --check; exit $?; }; done
# An alert is a message to a person. Marking it read is all this records — not
# that anything was done about it. Without the mark the same alert shows red on
# every later tick and the flag stops meaning "new".
for arg in "$@"; do [ "$arg" = "--read" ] && { python3 -c "
import sys; sys.path.insert(0, '$(cd "$(dirname "$0")" && pwd)/lib')
import where
from workspace import Workspace
shown = where.campaign() / 'ALERTS.shown'
try:
    count = int(shown.read_text('utf-8').strip())
except (FileNotFoundError, ValueError):
    print('nothing shown yet — nothing marked read')
else:
    Workspace(where.campaign()).alerts_read(count)
    print('alerts marked read')"; exit $?; }; done
# `--ledger 5` asked for five and got forty: the count was never passed on.
[ "${1:-}" = "--ledger" ] && { shift; exec python3 "$(dirname "$VIEW")/ledger_cli.py" "$@"; }
case "${1:-}" in
  -1) shift; python3 "$VIEW" "$@" ;;
  *)  trap 'echo; echo "stopped watching."; exit 0' INT
      while true; do
        clear 2>/dev/null || true
        python3 "$VIEW" ${1:+"$1"}
        echo
        echo "  (refreshing every ${REFRESH_SECONDS}s — Ctrl-C to stop)"
        sleep "$REFRESH_SECONDS"
      done ;;
esac
