#!/bin/bash
# Entrypoint script for Railway deployment
# Ensures PYTHONPATH is properly set before running the app

export PYTHONPATH=/app:$PYTHONPATH
cd /app

# Cron service: run lightweight sync script (no full app import)
if [ "$RAILWAY_SERVICE_NAME" = "brubru-cron-sync" ]; then
    exec python scripts/cron_sync.py
fi

# Main backend: run full app
exec python start.py
