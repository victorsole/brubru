#!/bin/bash
# Entrypoint script for Railway deployment
# Ensures PYTHONPATH is properly set before running the app

export PYTHONPATH=/app:$PYTHONPATH
cd /app

# Cron service: run lightweight sync script (no full app import)
# Each cron has its own Railway service so logs and schedule are isolated.
if [ "$RAILWAY_SERVICE_NAME" = "brubru-cron-sync" ]; then
    exec python scripts/cron_sync.py
fi

if [ "$RAILWAY_SERVICE_NAME" = "brubru-cron-authority-labels" ]; then
    exec python scripts/cron_sync_authority_labels.py
fi

# Main backend: run full app
exec python start.py
