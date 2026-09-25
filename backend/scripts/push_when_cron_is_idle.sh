#!/bin/zsh
# Push only when no cron tier is running.
#
# Railway redeploys on every push and the redeploy kills whatever the container is executing.
# Tiers run 12-30 minutes and the edge cuts the CLIENT connection at ~300s, so a tier that
# looks finished from outside is usually still working. /api/cron/runs-since reports it.
#
# The point of a script: on 25 September the check and the push were written as one
# `curl ... && git push` line, so the check printed "in flight" and the push went anyway.
# A check that cannot stop the action is decoration. This exits non-zero instead.
#
# Usage:  zsh scripts/push_when_cron_is_idle.sh [--wait] [git push args...]
set -e
BACKEND="${0:A:h:h}"
cd "$BACKEND"
SECRET=$(grep '^CRON_SECRET=' .env | cut -d= -f2-)
HOST="https://brubru-production.up.railway.app"
[ -n "$SECRET" ] || { print -u2 "no CRON_SECRET in $BACKEND/.env"; exit 3; }

WAIT=0
if [[ "$1" == "--wait" ]]; then WAIT=1; shift; fi

# Three states, printed as one word: IDLE, BUSY:<paths>, or UNREADABLE. An empty answer means
# the CHECK failed, not that the fleet is idle, and `set -e` must not turn that into a silent
# exit 1 that reads exactly like "busy".
in_flight() {
  local body
  body=$(curl -s -m 25 -H "Authorization: Bearer $SECRET" \
         "$HOST/api/cron/runs-since?minutes=60" 2>/dev/null) || true
  [ -n "$body" ] || { print "UNREADABLE"; return 0; }
  print -r -- "$body" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("UNREADABLE"); raise SystemExit
if "in_flight" not in data:
    print("UNREADABLE"); raise SystemExit
running = data.get("in_flight") or []
print("BUSY:" + ",".join(running) if running else "IDLE")
' 2>/dev/null || print "UNREADABLE"
}

for attempt in {1..60}; do
  STATE=$(in_flight)
  if [[ "$STATE" == "UNREADABLE" ]]; then
    print -u2 "cannot read cron state: refusing to push blind"
    exit 4
  fi
  if [[ "$STATE" == "IDLE" ]]; then
    print "cron idle; pushing"
    cd "${BACKEND:h}" && exec git push "$@"
  fi
  print "cron ${STATE}"
  [ "$WAIT" = 1 ] || exit 1
  sleep 60
done
print -u2 "still busy after 60 minutes"
exit 1
