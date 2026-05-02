#!/usr/bin/env python3
"""
Authority-label freshness gate for /news.

Reads `eu_authority_labels` row count + per-NAL distribution, compares
against a baseline saved in `data/eu_vocabularies/labels_baseline.json`,
and flags drift.

What "drift" means here:
  - Total row count fell >5% week-over-week → Cellar regression suspected
  - A specific NAL has zero rows but had >0 in baseline → that NAL broke
  - Last sync was >7 days ago (cron jammed)

Output (stdout, JSON):
    {
        "checked_at": "...",
        "total_rows": N,
        "by_nal": {"corporate-body": K, ...},
        "by_lang": {"en": K, ...},
        "baseline_age_days": M,
        "drift": {
            "total_drop_pct": -3.2,
            "missing_nals": [],
            "stale_sync_days": 1
        },
        "verdict": "ok" | "warn" | "fail"
    }

Exit code:
    0 - verdict="ok" (within tolerance)
    1 - verdict="warn" (small drift, log but don't block /news)
    2 - verdict="fail" (>5% drop OR a NAL went to zero — block /news Step 1)

Run:
    python3.12 backend/scripts/check_authority_labels_freshness.py

Cadence: every /news run, free piggyback (Step 1.freshness).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

BASELINE_PATH = ROOT / "data" / "eu_vocabularies" / "labels_baseline.json"
DROP_THRESHOLD_PCT = -5.0  # >5% drop = fail
STALE_DAYS_THRESHOLD = 7

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("labels-freshness")


def _query_state(db) -> Dict[str, Any]:
    total = db.execute(text("SELECT COUNT(*) FROM eu_authority_labels")).scalar() or 0

    by_nal_rows = db.execute(
        text(
            """
            SELECT
                COALESCE(source_dataset_uri, 'unknown') AS dataset,
                COUNT(*) AS n
            FROM eu_authority_labels
            GROUP BY source_dataset_uri
            ORDER BY n DESC
            """
        )
    ).all()
    by_nal = {row.dataset.rsplit("/", 1)[-1]: int(row.n) for row in by_nal_rows}

    by_lang_rows = db.execute(
        text("SELECT lang, COUNT(*) AS n FROM eu_authority_labels GROUP BY lang ORDER BY n DESC")
    ).all()
    by_lang = {row.lang: int(row.n) for row in by_lang_rows}

    last_sync_row = db.execute(
        text("SELECT MAX(fetched_at) FROM eu_authority_labels")
    ).scalar()
    last_sync_iso = last_sync_row.isoformat() if last_sync_row else None
    stale_sync_days = None
    if last_sync_row:
        stale_sync_days = (datetime.now(timezone.utc) - last_sync_row.replace(tzinfo=timezone.utc)).days

    return {
        "total_rows": int(total),
        "by_nal": by_nal,
        "by_lang": by_lang,
        "last_sync": last_sync_iso,
        "stale_sync_days": stale_sync_days,
    }


def _load_baseline() -> Dict[str, Any]:
    if not BASELINE_PATH.exists():
        return {}
    return json.loads(BASELINE_PATH.read_text())


def _save_baseline(state: Dict[str, Any]) -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["snapshotted_at"] = datetime.now(timezone.utc).isoformat()
    BASELINE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def _compute_drift(curr: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    base_total = baseline.get("total_rows", 0)
    curr_total = curr["total_rows"]

    if base_total > 0:
        drop_pct = ((curr_total - base_total) / base_total) * 100.0
    else:
        drop_pct = None  # First run; no baseline.

    missing_nals: List[str] = []
    for nal, base_count in (baseline.get("by_nal") or {}).items():
        if base_count > 0 and curr["by_nal"].get(nal, 0) == 0:
            missing_nals.append(nal)

    snapshotted_at = baseline.get("snapshotted_at")
    age_days = None
    if snapshotted_at:
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(snapshotted_at)
            age_days = age.days
        except ValueError:
            pass

    return {
        "total_drop_pct": round(drop_pct, 2) if drop_pct is not None else None,
        "missing_nals": missing_nals,
        "baseline_age_days": age_days,
        "stale_sync_days": curr.get("stale_sync_days"),
    }


def _verdict(drift: Dict[str, Any], curr_total: int) -> str:
    if curr_total == 0:
        # Empty table — pre-first-sync state. Warn, don't fail.
        return "warn"
    if drift["total_drop_pct"] is not None and drift["total_drop_pct"] < DROP_THRESHOLD_PCT:
        return "fail"
    if drift["missing_nals"]:
        return "fail"
    if (drift.get("stale_sync_days") or 0) > STALE_DAYS_THRESHOLD:
        return "fail"
    if drift["total_drop_pct"] is not None and drift["total_drop_pct"] < 0:
        return "warn"
    return "ok"


def main() -> int:
    db = SessionLocal()
    try:
        curr = _query_state(db)
    finally:
        db.close()

    baseline = _load_baseline()
    drift = _compute_drift(curr, baseline)
    verdict = _verdict(drift, curr["total_rows"])

    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        **curr,
        "drift": drift,
        "verdict": verdict,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Always update baseline on a clean (or warn-only) run so we track
    # the rolling state. On "fail", *don't* update so the next run still
    # sees the regression.
    if verdict in ("ok", "warn"):
        _save_baseline(curr)

    return {"ok": 0, "warn": 1, "fail": 2}[verdict]


if __name__ == "__main__":
    sys.exit(main())
