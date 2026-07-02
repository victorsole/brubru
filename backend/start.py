#!/usr/bin/env python3
"""
Startup script for Cloud Run deployment.
Sets up Python path before importing any application modules.
"""

import sys
import os

# Ensure the application directory is in Python path BEFORE any imports
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Set PYTHONPATH environment variable for any subprocesses
os.environ['PYTHONPATH'] = app_dir

# Now import the app (with path already set)
from main import app

# Run with uvicorn
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(
        app,  # Pass the app object directly, not as string
        host="0.0.0.0",
        port=port,
        limit_concurrency=100,
        # limit_max_requests removed 2 Jul 2026: on a single-process uvicorn.run
        # (no worker supervisor) it forced a full container cold-start every
        # 10,000 requests, each restart a multi-second outage while the app
        # reloaded 401 KB guides. Latent full-outage trigger; removed.
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
