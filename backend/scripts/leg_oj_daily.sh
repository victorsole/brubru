#!/bin/zsh
# Daily update of docs/LEG_2026-10 and its table from the OJ L series (launchd: eu.beresol.brubru.leg-oj-daily).
#
# Runs update_leg_from_oj.py --apply: each new OJ L legal act gets the export's folder, the table (CSV + Excel) is
# rebuilt, every decision goes to the ledger daily_updates.csv. The dump and the table are gitignored and live only
# in the main checkout, so launchd passes their paths:
#   LEG_DUMP           docs/LEG_2026-10 of the main checkout
#   LEG_TABLE          backend/data/leg_2026-10_table of the main checkout
#   LEG_LOG_DIR        where the run logs go
#   LEG_RECALC_SCRIPT  optional: the xlsx skill's recalc.py, so the Excel formulas carry values
#   PY                 optional: the interpreter (default /opt/anaconda3/bin/python3.12)
# launchd runs this file from a worktree kept at origin/main, so the job runs the pushed code. Writes no database.

set -u
BACKEND="${0:A:h:h}"
PY="${PY:-/opt/anaconda3/bin/python3.12}"
LOCK="/tmp/brubru_leg_oj_daily.lock"

for v in LEG_DUMP LEG_TABLE LEG_LOG_DIR; do
    if [ -z "${(P)v:-}" ]; then echo "[ERROR] $v is not set"; exit 2; fi
done
mkdir -p "$LEG_LOG_DIR"
LOG="$LEG_LOG_DIR/daily_$(date +%Y%m%d_%H%M).log"
exec >> "$LOG" 2>&1

echo "[START] $(date '+%Y-%m-%d %H:%M:%S') code $(git -C "$BACKEND" rev-parse --short HEAD 2>/dev/null)"

# Single-instance guard (stale after 4 h).
if [ -f "$LOCK" ] && [ -n "$(find "$LOCK" -mmin -240 2>/dev/null)" ]; then
    echo "[SKIP] lockfile fresh, another run in progress"; exit 0
fi
touch "$LOCK"
trap 'rm -f "$LOCK"' EXIT

cd "$BACKEND" || exit 1
"$PY" -u scripts/update_leg_from_oj.py --apply --dump "$LEG_DUMP" --out "$LEG_TABLE"
rc=$?

if [ $rc -ne 0 ]; then
    # silence is not success: a failed day stays open in the ledger and is read again; say so on screen too
    /usr/bin/osascript -e "display notification \"LEG_2026-10 daily update failed (exit $rc). Log: $LOG\" with title \"Brubru\"" 2>/dev/null
fi
echo "[END] $(date '+%Y-%m-%d %H:%M:%S') exit $rc"
exit $rc
