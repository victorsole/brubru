"""
EFPIA tenant-specific API surface.

GET /api/efpia/daily-candidates -- ranked feed of items scraped from EFPIA's
  pharma/health source map (DG SANTE, DG GROW, EP SANT, EMA). This is the pool
  the next morning's Brubru EFPIA Brief is curated from.

Auth: bearer JWT required, the user must resolve to the 'efpia' audience via
backend/data/audience_users.json. Anyone else gets 403.

Created 28 May 2026 as part of the EFPIA pilot (28 May - 28 June).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from services.audience import resolve_audience

router = APIRouter(prefix="/api/efpia", tags=["EFPIA"])


_AUDIENCE = "efpia"
_DEFAULT_WINDOW_HOURS = 72
_MAX_LIMIT = 200


class CandidateItem(BaseModel):
    id: str
    source_id: str
    institution: str
    bucket: str
    kind: str
    item_url: str
    item_title: str
    item_summary: Optional[str] = None
    item_published_at: Optional[datetime] = None
    scraped_at: datetime
    relevance_score: int
    metadata: dict = {}


class CandidatesResponse(BaseModel):
    audience: str
    window_hours: int
    bucket: str
    min_relevance: int
    total: int
    items: List[CandidateItem]


def _require_efpia_user(
    db: Session,
    authorization: Optional[str],
) -> str:
    """
    Resolve the bearer JWT to a user and require them to belong to the
    'efpia' audience. 401 if no token / bad token, 403 if not EFPIA.
    """

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token")

    try:
        from api.auth import SECRET_KEY, ALGORITHM
        from jose import jwt, JWTError
        from models.user import User
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"auth subsystem unavailable: {exc}")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing sub")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active or not getattr(user, "email", None):
        raise HTTPException(status_code=401, detail="User not found")

    audience = resolve_audience(user.email)
    if audience != _AUDIENCE:
        raise HTTPException(
            status_code=403,
            detail="This endpoint is reserved for the EFPIA pilot audience.",
        )

    return user.email


@router.get("/daily-candidates", response_model=CandidatesResponse)
def get_daily_candidates(
    since_hours: int = Query(default=_DEFAULT_WINDOW_HOURS, ge=1, le=720, description="Look-back window in hours."),
    bucket: str = Query(default="all", description="Filter by source bucket: dg_sante, dg_grow, ep_sant, ema, horizontal_ec, or all."),
    institution: str = Query(default="all", description="Filter by institution: EC, EP, EMA, or all."),
    min_relevance: int = Query(default=50, ge=0, le=100, description="Minimum relevance score to include."),
    limit: int = Query(default=40, ge=1, le=_MAX_LIMIT, description="Maximum items to return."),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """
    Ranked feed of scraped EU pharma/health items for EFPIA brief curation.

    Default behaviour returns the last 72 hours, all buckets, all institutions,
    relevance >= 50, ordered by (relevance_score DESC, item_published_at DESC,
    scraped_at DESC). Tomorrow morning's brief curator (a human or a future
    propose-headlines helper) picks 5 from the top of this list.
    """

    _require_efpia_user(db, authorization)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    params: dict = {
        "cutoff": cutoff,
        "min_relevance": min_relevance,
        "limit": limit,
    }

    where_clauses = [
        "scraped_at >= :cutoff",
        "relevance_score >= :min_relevance",
    ]
    if bucket and bucket.lower() != "all":
        where_clauses.append("bucket = :bucket")
        params["bucket"] = bucket.lower()
    if institution and institution.lower() != "all":
        where_clauses.append("institution = :institution")
        params["institution"] = institution.upper()

    where_sql = " AND ".join(where_clauses)

    sql = text(
        f"""
        SELECT id, source_id, institution, bucket, kind, item_url, item_title,
               item_summary, item_published_at, scraped_at, relevance_score, metadata
        FROM efpia_scraped_items
        WHERE {where_sql}
        ORDER BY relevance_score DESC,
                 COALESCE(item_published_at, scraped_at) DESC,
                 scraped_at DESC
        LIMIT :limit
        """
    )

    rows = db.execute(sql, params).mappings().all()

    items: List[CandidateItem] = []
    for row in rows:
        items.append(
            CandidateItem(
                id=str(row["id"]),
                source_id=row["source_id"],
                institution=row["institution"],
                bucket=row["bucket"],
                kind=row["kind"],
                item_url=row["item_url"],
                item_title=row["item_title"],
                item_summary=row["item_summary"],
                item_published_at=row["item_published_at"],
                scraped_at=row["scraped_at"],
                relevance_score=row["relevance_score"],
                metadata=row["metadata"] or {},
            )
        )

    return CandidatesResponse(
        audience=_AUDIENCE,
        window_hours=since_hours,
        bucket=bucket.lower(),
        min_relevance=min_relevance,
        total=len(items),
        items=items,
    )


@router.get("/sources")
def get_sources(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """
    Describe the EFPIA source catalogue (tier-1 priority list + per-bucket
    counts + last-scrape timestamp per source). Useful for tomorrow's
    /morning routine to confirm the pool is fresh.
    """

    _require_efpia_user(db, authorization)

    from services import efpia_scraper

    catalogue = efpia_scraper.load_sources()
    last_scrape = db.execute(
        text(
            """
            SELECT source_id,
                   MAX(scraped_at)         AS last_scraped_at,
                   COUNT(*)                AS items_total,
                   MAX(item_published_at)  AS most_recent_publication
            FROM efpia_scraped_items
            GROUP BY source_id
            """
        )
    ).mappings().all()
    by_source = {r["source_id"]: dict(r) for r in last_scrape}

    sources_out = []
    for src in catalogue.get("sources", []):
        stats = by_source.get(src["id"], {})
        sources_out.append(
            {
                "id": src["id"],
                "label": src.get("label"),
                "institution": src.get("institution"),
                "bucket": src.get("bucket"),
                "kind": src.get("kind"),
                "cadence": src.get("cadence"),
                "in_tier1": src["id"] in (catalogue.get("tier1_priority_sources") or []),
                "items_total": int(stats.get("items_total") or 0),
                "last_scraped_at": stats.get("last_scraped_at"),
                "most_recent_publication": stats.get("most_recent_publication"),
            }
        )

    return {
        "tier1_priority_sources": catalogue.get("tier1_priority_sources") or [],
        "deprecated_from_tier1": catalogue.get("deprecated_from_tier1") or {},
        "total_sources": len(sources_out),
        "sources": sources_out,
    }
