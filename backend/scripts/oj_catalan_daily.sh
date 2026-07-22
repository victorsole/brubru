#!/bin/zsh
# Daily My OJ Catalan run (launchd: eu.beresol.brubru.oj-catalan).
#
# 1. backfill_oj_translations.py  — new OJ titles + explanations -> Catalan
# 2. translate_oj_daily_acts.py   — new L-series full acts -> corpus pages
# 3. deploy_catalan_backlog.py    — push everything undeployed to SiteGround
#
# Softcatala only, local, free. Logs to backend/logs/oj_translate/.
# A lockfile + pgrep guards prevent overlap with an interactive session
# already running the same scripts.

set -u
BACKEND="/Users/victorsole/Documents/GitHub/brubru/backend"
PY="/opt/anaconda3/bin/python3.12"
LOCK="/tmp/brubru_oj_catalan_daily.lock"
LOG_DIR="$BACKEND/logs/oj_translate"
LOG="$LOG_DIR/daily_$(date +%Y%m%d_%H%M).log"

mkdir -p "$LOG_DIR"
exec >> "$LOG" 2>&1

echo "[START] $(date '+%Y-%m-%d %H:%M:%S')"

# Single-instance guard (stale after 4h).
if [ -f "$LOCK" ] && [ -n "$(find "$LOCK" -mmin -240 2>/dev/null)" ]; then
    echo "[SKIP] lockfile fresh, another run in progress"; exit 0
fi
touch "$LOCK"
trap 'rm -f "$LOCK"' EXIT

cd "$BACKEND" || exit 1

# Skip any stage whose script is already running in an interactive session.
if pgrep -f backfill_oj_translations.py > /dev/null; then
    echo "[SKIP] backfill_oj_translations.py already running"
else
    echo "[STEP 1] OJ titles -> Catalan"
    "$PY" -u scripts/backfill_oj_translations.py --limit 200
fi

if pgrep -f translate_oj_daily_acts.py > /dev/null; then
    echo "[SKIP] translate_oj_daily_acts.py already running"
else
    echo "[STEP 2] OJ full acts -> Catalan corpus"
    "$PY" -u scripts/translate_oj_daily_acts.py --limit 40
fi

if pgrep -f deploy_catalan_backlog.py > /dev/null; then
    echo "[SKIP] deploy_catalan_backlog.py already running"
else
    echo "[STEP 3] Deploy to SiteGround"
    "$PY" -u scripts/deploy_catalan_backlog.py
fi

echo "[END] $(date '+%Y-%m-%d %H:%M:%S')"
