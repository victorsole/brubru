"""Language analytics endpoints.

Powers the "are EU institutions talking about Catalan/Basque/Galician more
or less over time?" widget that lives in MEUB Dashboard for users whose
private guide is linguistic-rights focused. Also exposes a "recent Catalan
EU acquis" widget powered by Brubru's own Catalan translation pipeline
(28,513 OJ publications translated locally to Catalan and published at
/legislacio-ue-catala/).

All endpoints are read-only and JWT-authenticated (uses the optional dev
helper that 401s if no JWT in prod).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from .auth_optional import get_current_user_dev as get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Language Analytics"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LanguageMentionsMonthBucket(BaseModel):
    month: date
    keyword: str
    count: int


class LanguageMentionsResponse(BaseModel):
    keywords: List[str]
    since: date
    buckets: List[LanguageMentionsMonthBucket]
    total: int
    note: str = "Counts include eu_laws + texts_adopted + legislative_carriages + rss_entries. Each row is counted once per keyword it matches."


class CatalanAcquisItem(BaseModel):
    celex: str
    title: Optional[str] = None
    doc_type: Optional[str] = None
    date: Optional[date] = None
    catalan_url: str  # /legislacio-ue-catala/<celex>/


class CatalanAcquisResponse(BaseModel):
    total_published: int
    recent: List[CatalanAcquisItem]


# ---------------------------------------------------------------------------
# Mentions timeline
# ---------------------------------------------------------------------------


_DEFAULT_KEYWORDS = ["Catalan", "Basque", "Galician", "Aranese"]


@router.get("/language-mentions", response_model=LanguageMentionsResponse)
async def language_mentions(
    keywords: Optional[str] = Query(
        default=None,
        description="Comma-separated keywords. Defaults to Catalan,Basque,Galician,Aranese.",
    ),
    since: Optional[date] = Query(
        default=None,
        description="ISO date floor. Defaults to 2020-01-01.",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kw_list = (
        [k.strip() for k in keywords.split(",") if k.strip()]
        if keywords
        else _DEFAULT_KEYWORDS
    )
    floor = since or date(2020, 1, 1)

    # For each keyword we do four scans (one per corpus) bucketed by month.
    # texts_adopted uses adoption_date, legislative_carriages uses
    # first_seen, rss_entries uses published_at, eu_laws uses date.
    out: list[dict] = []
    total = 0
    for kw in kw_list:
        pattern = f"%{kw}%"

        # eu_laws via search_vector for accuracy + speed
        rows = db.execute(
            text(
                """
                SELECT date_trunc('month', date)::date AS month, count(*)::int AS n
                FROM eu_laws
                WHERE search_vector @@ websearch_to_tsquery('simple', :kw)
                  AND date >= :since
                GROUP BY 1
                """
            ),
            {"kw": kw, "since": floor},
        ).all()
        for r in rows:
            out.append({"month": r[0], "keyword": kw, "count": r[1]})
            total += r[1]

        # texts_adopted
        rows = db.execute(
            text(
                """
                SELECT date_trunc('month', adoption_date)::date AS month, count(*)::int AS n
                FROM texts_adopted
                WHERE (title ILIKE :p OR description ILIKE :p OR substring(coalesce(full_text,'') from 1 for 50000) ILIKE :p)
                  AND adoption_date >= :since
                GROUP BY 1
                """
            ),
            {"p": pattern, "since": floor},
        ).all()
        for r in rows:
            out.append({"month": r[0], "keyword": kw, "count": r[1]})
            total += r[1]

        # legislative_carriages
        rows = db.execute(
            text(
                """
                SELECT date_trunc('month', first_seen)::date AS month, count(*)::int AS n
                FROM legislative_carriages
                WHERE (title ILIKE :p OR description ILIKE :p)
                  AND first_seen >= :since
                GROUP BY 1
                """
            ),
            {"p": pattern, "since": floor},
        ).all()
        for r in rows:
            out.append({"month": r[0], "keyword": kw, "count": r[1]})
            total += r[1]

        # rss_entries
        rows = db.execute(
            text(
                """
                SELECT date_trunc('month', published_at)::date AS month, count(*)::int AS n
                FROM rss_entries
                WHERE (title ILIKE :p OR coalesce(summary,'') ILIKE :p)
                  AND published_at >= :since
                GROUP BY 1
                """
            ),
            {"p": pattern, "since": floor},
        ).all()
        for r in rows:
            out.append({"month": r[0], "keyword": kw, "count": r[1]})
            total += r[1]

    # Collapse same-month-same-keyword duplicates (since we ran 4 corpora)
    merged: dict[tuple, int] = {}
    for b in out:
        key = (b["month"], b["keyword"])
        merged[key] = merged.get(key, 0) + b["count"]
    buckets = [
        LanguageMentionsMonthBucket(month=m, keyword=k, count=n)
        for (m, k), n in sorted(merged.items())
    ]
    return LanguageMentionsResponse(
        keywords=kw_list, since=floor, buckets=buckets, total=total
    )


# ---------------------------------------------------------------------------
# Recent Catalan acquis (Brubru's own translation pipeline)
# ---------------------------------------------------------------------------


@router.get("/catalan-acquis-recent", response_model=CatalanAcquisResponse)
async def catalan_acquis_recent(
    limit: int = Query(default=8, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the most recently Catalan-translated EU legal acts and the
    total number of acts Brubru has translated so far. Backs the
    "Catalan Acquis" widget that demonstrates Brubru is the only platform
    publishing the EU acquis in Catalan.

    Source: `eu_laws` joined with the catalan translation publication
    state stored in `extra_metadata->>'catalan_translated_at'`.
    """
    total_row = db.execute(
        text(
            """
            SELECT count(*)::int FROM eu_laws
            WHERE extra_metadata ? 'catalan_translated_at'
            """
        )
    ).scalar() or 0

    rows = db.execute(
        text(
            """
            SELECT celex, title, doc_type, date,
                   extra_metadata->>'catalan_translated_at' AS translated_at
            FROM eu_laws
            WHERE extra_metadata ? 'catalan_translated_at'
            ORDER BY (extra_metadata->>'catalan_translated_at') DESC NULLS LAST
            LIMIT :lim
            """
        ),
        {"lim": limit},
    ).mappings().all()

    items = [
        CatalanAcquisItem(
            celex=r["celex"],
            title=r["title"],
            doc_type=r["doc_type"],
            date=r["date"],
            catalan_url=f"/legislacio-ue-catala/{r['celex']}/",
        )
        for r in rows
        if r["celex"]
    ]
    return CatalanAcquisResponse(total_published=total_row, recent=items)
