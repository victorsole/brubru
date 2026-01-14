#!/bin/bash
# Entrypoint script for Railway deployment
# Ensures PYTHONPATH is properly set before running the app

export PYTHONPATH=/app:$PYTHONPATH
cd /app
exec python start.py
