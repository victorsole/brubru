"""
EFPIA daily brief: ingestion of the headlines JSON into daily_briefs rows.

Reads:  backend/data/efpia_brief/YYYY-MM-DD.json
Writes: daily_briefs rows tagged audience='efpia' for the same date.

This makes the same content the email sends available inside Brubru chat (card
+ EU CONTEXT) and downstream features (Dashboard widget, MEUB document).

Idempotent: DELETE WHERE audience='efpia' AND brief_date=:date before INSERT.

Created 28 May 2026 after the EFPIA pilot kickoff. See
memory/feedback_chat_must_use_anthropic.md for why this lives in the chat path.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from core.database import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

_HEADLINES_DIR = _BACKEND_ROOT / "data" / "efpia_brief"
_PRIORITY_FILES = _BACKEND_ROOT / "data" / "efpia_brief" / "priority_files.json"

AUDIENCE = "efpia"
CATEGORY = "pharma_health"
SOURCE_TAG = "Brubru EFPIA Brief"


def _load_headlines(issue_date: str) -> dict:
    path = _HEADLINES_DIR / f"{issue_date}.json"
    if not path.is_file():
        raise SystemExit(f"no headlines file at {path}")
    with path.open() as fh:
        return json.load(fh)


def _load_priority_files() -> dict:
    if not _PRIORITY_FILES.is_file():
        raise SystemExit(f"missing priority files config at {_PRIORITY_FILES}")
    with _PRIORITY_FILES.open() as fh:
        return json.load(fh)


def _build_priority_files_summary(priority: dict) -> str:
    bits = []
    for pf in priority["files"]:
        ref = pf.get("oeil_ref") or (pf.get("celex") and f"CELEX {pf['celex']}") or ""
        status = pf.get("status_note", "").rstrip(".")
        if ref:
            bits.append(f"{pf['label']} ({ref}). {status}.")
        else:
            bits.append(f"{pf['label']}. {status}.")
    return "Brubru is monitoring these EFPIA priority files today: " + "; ".join(bits)


def ingest(issue_date: str, dry_run: bool = False) -> int:
    payload = _load_headlines(issue_date)
    priority = _load_priority_files()
    headlines = payload.get("headlines") or []
    if len(headlines) != 5:
        raise SystemExit(f"expected exactly 5 headlines, got {len(headlines)}")

    brief_date = datetime.strptime(issue_date, "%Y-%m-%d").date()

    db = SessionLocal()
    try:
        deleted = db.execute(
            text("DELETE FROM daily_briefs WHERE audience = :aud AND brief_date = :d"),
            {"aud": AUDIENCE, "d": brief_date},
        ).rowcount or 0

        rows_written = 0

        # Anchor card: priority=0 makes it the headline card in the chat surface.
        anchor_headline = f"Brubru EFPIA Brief, {payload.get('day_of_week', '')} {brief_date.strftime('%-d %B %Y')}".strip().rstrip(',')
        anchor_snippet = payload.get("hero_intro") or (
            "Five EU pharma and health items today, plus Brubru's running monitor of your priority files."
        )
        db.execute(
            text(
                """
                INSERT INTO daily_briefs (id, brief_date, headline, url, source, category, priority, snippet, suggested_query, created_at, audience)
                VALUES (:id, :d, :h, :u, :src, :cat, :p, :sn, :sq, :ts, :aud)
                """
            ),
            {
                "id": str(uuid4()),
                "d": brief_date,
                "h": anchor_headline,
                "u": "https://brubru.beresol.eu/main",
                "src": SOURCE_TAG,
                "cat": CATEGORY,
                "p": 0,
                "sn": anchor_snippet,
                "sq": "Give me today's Brubru EFPIA Brief in full.",
                "ts": datetime.now(timezone.utc),
                "aud": AUDIENCE,
            },
        )
        rows_written += 1

        for idx, h in enumerate(headlines):
            priority_value = 100 - idx  # 100, 99, 98, 97, 96
            db.execute(
                text(
                    """
                    INSERT INTO daily_briefs (id, brief_date, headline, url, source, category, priority, snippet, suggested_query, created_at, audience)
                    VALUES (:id, :d, :h, :u, :src, :cat, :p, :sn, :sq, :ts, :aud)
                    """
                ),
                {
                    "id": str(uuid4()),
                    "d": brief_date,
                    "h": h["title"],
                    "u": h.get("feature_url") or "https://brubru.beresol.eu/main",
                    "src": h.get("source") or SOURCE_TAG,
                    "cat": CATEGORY,
                    "p": priority_value,
                    "sn": h.get("snippet") or "",
                    "sq": h.get("ask") or "",
                    "ts": datetime.now(timezone.utc),
                    "aud": AUDIENCE,
                },
            )
            rows_written += 1

        # Synthesis row for the priority-files monitor (priority=50).
        db.execute(
            text(
                """
                INSERT INTO daily_briefs (id, brief_date, headline, url, source, category, priority, snippet, suggested_query, created_at, audience)
                VALUES (:id, :d, :h, :u, :src, :cat, :p, :sn, :sq, :ts, :aud)
                """
            ),
            {
                "id": str(uuid4()),
                "d": brief_date,
                "h": "Brubru is tracking your EFPIA priority files",
                "u": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative#efpia-priority-files",
                "src": SOURCE_TAG,
                "cat": CATEGORY,
                "p": 50,
                "sn": _build_priority_files_summary(priority),
                "sq": "Where are my EFPIA priority files today?",
                "ts": datetime.now(timezone.utc),
                "aud": AUDIENCE,
            },
        )
        rows_written += 1

        if dry_run:
            db.rollback()
            print(f"[DRY RUN] would delete {deleted} stale rows and insert {rows_written} rows for {brief_date}.")
        else:
            db.commit()
            print(f"[OK] EFPIA brief ingested for {brief_date}: deleted {deleted}, inserted {rows_written}.")

        return 0
    finally:
        db.close()


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def main() -> int:
    p = argparse.ArgumentParser(description="Ingest the EFPIA daily brief JSON into daily_briefs.")
    p.add_argument("--date", default=_today_iso(), help="Issue date YYYY-MM-DD.")
    p.add_argument("--dry-run", action="store_true", help="Run all reads and inserts, then ROLLBACK.")
    args = p.parse_args()
    return ingest(args.date, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
