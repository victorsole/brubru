"""
Brubru MCP corpus stats — computed at runtime, never hardcoded.

Every number the MCP surface states to a caller (laws, guides, procedures,
calendar events, EPRS publications) is read live from the database + the
KnowledgeLoader here, then cached for an hour. This kills the recurring
"the server advertises 28,505 laws but the DB has 16,998" drift: there is
one function, it reads the source of truth, and the descriptions/instructions
call it instead of embedding a literal.

Design notes:
    - Cheap: five COUNT(*) queries + one guide-dir load, cached TTL_SECONDS.
    - Safe: if the DB is unreachable at call time (cold start, network blip)
      we return the last good snapshot, or FALLBACK constants if we never
      succeeded. The MCP must never 500 because a count could not be read.
    - Honest: the law figure is DISTINCT celex in eu_laws (what search
      actually covers), not the LEG_2025-11 bulk-export corpus triple.
"""

from __future__ import annotations

import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)

TTL_SECONDS = 3600

# Last-resort values if the DB has never been reachable in this process.
# Deliberately close to reality (July 2026) so a cold-start caller is not
# badly misled, but the live query overrides these within the first call.
FALLBACK: Dict[str, int] = {
    "laws": 16998,
    "guides": 538,
    "procedures": 2628,
    "calendar_events": 3830,
    "eprs_publications": 521,
}

_cache: Dict[str, int] = {}
_cache_at: float = 0.0


def _compute() -> Dict[str, int]:
    """Read every count from its source of truth. Raises on DB failure."""
    from sqlalchemy import text

    from core.database import SessionLocal

    stats: Dict[str, int] = {}

    db = SessionLocal()
    try:
        stats["laws"] = int(
            db.execute(
                text("SELECT count(DISTINCT celex) FROM eu_laws WHERE celex IS NOT NULL")
            ).scalar()
            or 0
        )
        stats["procedures"] = int(
            db.execute(text("SELECT count(*) FROM legislative_carriages")).scalar() or 0
        )
        stats["calendar_events"] = int(
            db.execute(text("SELECT count(*) FROM eu_calendar_events")).scalar() or 0
        )
        stats["eprs_publications"] = int(
            db.execute(text("SELECT count(*) FROM eprs_publications")).scalar() or 0
        )
    finally:
        db.close()

    # Guides come from the KnowledgeLoader, not the DB.
    try:
        from knowledge_base.knowledge_loader import KnowledgeLoader

        loader = KnowledgeLoader()
        loader.load_all()
        stats["guides"] = len(loader.guides)
    except Exception:  # noqa: BLE001
        stats["guides"] = FALLBACK["guides"]

    return stats


def get_corpus_stats(force: bool = False) -> Dict[str, int]:
    """Return {laws, guides, procedures, calendar_events, eprs_publications}.

    Cached for TTL_SECONDS. Never raises: on DB failure returns the last good
    snapshot, or FALLBACK if we have never succeeded.
    """
    global _cache, _cache_at

    now = time.time()
    if not force and _cache and (now - _cache_at) < TTL_SECONDS:
        return dict(_cache)

    try:
        fresh = _compute()
        _cache = fresh
        _cache_at = now
        return dict(fresh)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[mcp.stats] live count failed (%s); serving cached/fallback", exc)
        return dict(_cache) if _cache else dict(FALLBACK)


def format_summary() -> str:
    """One-line human summary used in server instructions / handshakes."""
    s = get_corpus_stats()
    return (
        f"{s['laws']:,} EU laws, {s['guides']:,} curated knowledge guides, "
        f"{s['procedures']:,} live legislative procedures, "
        f"{s['calendar_events']:,} calendar events, "
        f"{s['eprs_publications']:,} EPRS publications"
    )
