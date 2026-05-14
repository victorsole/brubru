#!/bin/bash
# Entrypoint script for Railway deployment
# Ensures PYTHONPATH is properly set before running the app

export PYTHONPATH=/app:$PYTHONPATH
cd /app

# Cron service: single-service dispatcher (14 May 2026 onwards).
# brubru-cron-sync wakes once per hour (Railway CRON_SCHEDULE = "0 * * * *") and
# the dispatcher decides which tier(s) to fire based on the current UTC time.
# See backend/scripts/cron_dispatch.py + backend/config/sync_cadence.json.
if [ "$RAILWAY_SERVICE_NAME" = "brubru-cron-sync" ]; then
    exec python scripts/cron_dispatch.py
fi

# Legacy: kept for back-compat if the service still exists in Railway.
if [ "$RAILWAY_SERVICE_NAME" = "brubru-cron-authority-labels" ]; then
    exec python scripts/cron_sync_authority_labels.py
fi

# Main backend: run full app
exec python start.py
