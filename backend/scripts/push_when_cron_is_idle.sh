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
#         zsh scripts/push_when_cron_is_idle.sh --state     # print the state word and exit 0; pushes nothing
#
# --wait waits as long as the running tier PROGRESSES (25 Nov 2026): the warm tier ran 2 h 15 min that day
# (14:09-16:25 UTC) and the old cap of 60 one-minute attempts gave up twice while it was still finishing
# sources. It gives up when the running tier has shown no progress for STALL_MINUTES (a hung tier needs a
# person, not a push that kills it: exit 5), or after MAX_WAIT_MINUTES in all (exit 1).
# Exit: 0 pushed (or --state), 1 busy, 3 no secret, 4 state unreadable, 5 the running tier looks hung.
set -e
BACKEND="${0:A:h:h}"
cd "$BACKEND"
STALL_MINUTES=45
MAX_WAIT_MINUTES=300
HOST="https://brubru-production.up.railway.app"
# PUSH_GATE_PAYLOAD_FILE replaces the live answer with a file: tests only.
if [[ -z "$PUSH_GATE_PAYLOAD_FILE" ]]; then
  SECRET=$(grep '^CRON_SECRET=' .env 2>/dev/null | cut -d= -f2-)
  [ -n "$SECRET" ] || { print -u2 "no CRON_SECRET in $BACKEND/.env"; exit 3; }
fi

WAIT=0
STATE_ONLY=0
if [[ "$1" == "--state" ]]; then STATE_ONLY=1; shift; fi
if [[ "$1" == "--wait" ]]; then WAIT=1; shift; fi

# Three states, printed as one word: IDLE, BUSY:<paths>|<quiet>, or UNREADABLE. An empty answer means
# the CHECK failed, not that the fleet is idle, and `set -e` must not turn that into a silent
# exit 1 that reads exactly like "busy". <quiet> is how many minutes ago the running tier last showed
# progress (a source finished, or the tier started), NONE when nothing in the hour shows any, BG when only a
# background batch is running (it records no sources, so it cannot be judged hung).
in_flight() {
  local body
  if [[ -n "$PUSH_GATE_PAYLOAD_FILE" ]]; then
    body=$(cat "$PUSH_GATE_PAYLOAD_FILE" 2>/dev/null) || true
  else
    body=$(curl -s -m 25 -H "Authorization: Bearer $SECRET" \
           "$HOST/api/cron/runs-since?minutes=60" 2>/dev/null) || true
  fi
  [ -n "$body" ] || { print "UNREADABLE"; return 0; }
  print -r -- "$body" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("UNREADABLE"); raise SystemExit
if "in_flight" not in data:
    print("UNREADABLE"); raise SystemExit
# An economy batch runs as a background task after its request has returned, so it is in
# `background`, not `in_flight` (30 Oct 2026: a push cut economy batch 2 after 7 of 26 bodies).
running = (data.get("in_flight") or []) + (data.get("background") or [])
if not running:
    print("IDLE"); raise SystemExit
from datetime import datetime, timedelta
quiet = "BG"
if data.get("in_flight"):
    quiet = "NONE"
    try:
        now = datetime.fromisoformat(data["now"])
        marks = [datetime.fromisoformat(r["finished_at"]) for r in data.get("runs") or [] if r.get("finished_at")]
        marks += [now - timedelta(seconds=float(s)) for s in (data.get("in_flight_seconds") or {}).values()]
        if marks:
            quiet = str(max(0, int((now - max(marks)).total_seconds() // 60)))
    except (KeyError, ValueError, TypeError):
        quiet = "NONE"
print("BUSY:" + ",".join(running) + "|" + quiet)
' 2>/dev/null || print "UNREADABLE"
}

if [[ "$STATE_ONLY" == 1 ]]; then
  in_flight
  exit 0
fi

START=$(date +%s)
while (( ($(date +%s) - START) / 60 < MAX_WAIT_MINUTES )); do
  # Railway "Wait for CI" deploys 5-8 minutes AFTER the push, and the hourly dispatcher
  # starts its tiers at ~:03. A push between :48 and :02 lands the restart on top of them:
  # 7 Oct 2026, pushed at 10:58 "idle", deployed 11:05, journey_precompute cut mid-run and
  # the cron reported "Deploy crashed". Idle NOW is not idle when the deploy lands.
  MIN=$((10#$(date -u +%M)))
  # The dispatch starts the hour's tiers and economy batch as late as :07 (05:06 UTC on 30 Oct),
  # so until :10 an idle answer can be the moment before they start: 30 Oct, pushed 14:03:08
  # "idle", the 14:04:38 dispatch fired the fast and warm tiers, the deploy landed about 14:11
  # and cut both. From :10 they show in `in_flight` or `background`.
  if (( MIN >= 48 || MIN < 10 )); then
    print "the deploy would land on the hourly dispatch (minute $MIN); waiting"
    [ "$WAIT" = 1 ] || exit 1
    sleep 60
    continue
  fi
  STATE=$(in_flight)
  if [[ "$STATE" == "UNREADABLE" ]]; then
    print -u2 "cannot read cron state: refusing to push blind"
    exit 4
  fi
  if [[ "$STATE" == "IDLE" ]]; then
    print "cron idle; pushing"
    cd "${BACKEND:h}" && exec git push "$@"
  fi
  QUIET="${STATE##*|}"
  case "$QUIET" in
    BG) NOTE="a background batch, which records no progress" ;;
    NONE) NOTE="no progress shown in the last hour" ;;
    *) NOTE="last progress ${QUIET} min ago" ;;
  esac
  print "cron ${STATE%|*} ($NOTE)"
  [ "$WAIT" = 1 ] || exit 1
  if [[ "$QUIET" == "NONE" ]] || { [[ "$QUIET" == <-> ]] && (( QUIET >= STALL_MINUTES )); }; then
    print -u2 "a tier is running but has shown no progress for ${STALL_MINUTES}+ minutes: it may be hung. Read /api/cron/runs-since before pushing. Not pushing."
    exit 5
  fi
  sleep 60
done
print -u2 "still busy after ${MAX_WAIT_MINUTES} minutes"
exit 1
