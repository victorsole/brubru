"""Resolve DATABASE_URL the way a container can actually satisfy.

Six ingest scripts used to do this:

    db_url = open(ROOT / ".env").read().split("DATABASE_URL=")[1]...

which works on a laptop and raises `FileNotFoundError` on Railway, where the
value is an environment variable and there is no `.env` file on disk. That is
why the `warm` tier logged 8 consecutive `parl_questions` failures between 20
and 23 August 2026 while every local run of the same script passed.

Environment first, `.env` only as a developer convenience, and a message that
says which one was missing rather than a raw traceback.
"""
from __future__ import annotations

import os
from pathlib import Path


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    for candidate in (
        Path(__file__).resolve().parents[2] / ".env",   # repo root
        Path(__file__).resolve().parents[1] / ".env",   # backend/
    ):
        if candidate.is_file():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                if line.startswith("DATABASE_URL="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(
        "DATABASE_URL is not set and no .env file carries it. In a container "
        "this must come from the environment; locally, add it to .env."
    )
