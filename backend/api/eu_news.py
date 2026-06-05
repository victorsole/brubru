"""
MEUB News API — EU institutional news, PI-filterable, image-rich.

Reads eu_news_items (migration 101). Powers the Section-1 "News" tab: a featured
hero + a card feed. Phase-1 aligned: filtering goes through the shared PI-filter
builder (services/tracking/pi_filter.py) over the now-populated `policy_areas`
join key (+ DG + keyword recall), and a "My Tracked Files" lens flags/keeps news
topically related to the files the user follows (tracked_lens). Two registers:
`matches_interests` (soft, your Policy Interests) and `matches_tracked` (the
files you track).
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.eu_news_item import EuNewsItem
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import dgs_for_interests, keywords_for_interests
from services.tracking.pi_filter import AnchorSpec, build_pi_clause
from services.tracking.tracked_lens import tracked_anchors
from knowledge_base.eu_calendar_institutions import COMMISSION_DG_NAME
from .auth_optional import get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eu-news", tags=["EU News"])

# News exposes policy_areas (the canonical join key) + a DG + free text.
NEWS_SPEC = AnchorSpec(
    policy_areas_col="policy_areas",
    dg_col="commission_dg",
    keyword_cols=("title", "summary"),
)


def _soft_match(item: EuNewsItem, interests: set, dgs: set, keywords: List[str]) -> Optional[str]:
    """Why this item is in the user's interests (soft register), or None."""
    overlap = set(item.policy_areas or []) & interests
    if overlap:
        return "In your interests: " + ", ".join(sorted(overlap))
    if item.commission_dg and item.commission_dg in dgs:
        return f"Matches a department you follow ({item.commission_dg})"
    hay = f"{item.title or ''} {item.summary or ''}".lower()
    if any(k in hay for k in keywords):
        return "Mentions a topic in your interests"
    return None


def _tracked_match(item: EuNewsItem, tracked_pa: set) -> Optional[str]:
    """Why this item relates to a file the user tracks (hard-ish register), or None."""
    overlap = set(item.policy_areas or []) & tracked_pa
    if overlap:
        return "Related to files you track: " + ", ".join(sorted(overlap))
    return None


def _item_dict(e: EuNewsItem, interests: set, dgs: set, keywords: List[str], tracked_pa: set) -> dict:
    soft = _soft_match(e, interests, dgs, keywords)
    hard = _tracked_match(e, tracked_pa)
    return {
        "id": str(e.id),
        "title": e.title,
        "summary": e.summary,
        "news_date": e.news_date.isoformat() if e.news_date else None,
        "institution": e.institution,
        "commission_dg": e.commission_dg,
        "dg_name": COMMISSION_DG_NAME.get(e.commission_dg) if e.commission_dg else None,
        "item_type": e.item_type,
        "source_key": e.source_key,
        "policy_areas": list(e.policy_areas or []),
        "image_url": e.image_url,
        "source_url": e.source_url,
        "matches_interests": bool(soft),
        "interest_reason": soft,
        "matches_tracked": bool(hard),
        "tracked_reason": hard,
    }


@router.get("/items", summary="EU institutional news feed",
            description=(
                "**What it does**\nReturns the aggregated EU institutional news feed "
                "(Commission hub + every DG/agency newsroom + Parliament + outlets), "
                "image-rich and sorted newest-first, with a featured set for the hero.\n\n"
                "**When to use it**\nThe MEUB 'News' tab.\n\n"
                "**Input**\n`my_interests=true` keeps only news in your Policy Interests; "
                "`my_files=true` keeps only news related to the files you track; "
                "`institution`; `commission_dg`; `item_type`; `search`; `limit`/`offset`.\n\n"
                "**You get back**\nNews cards (title, summary, image, DG, date, areas, link) "
                "each flagged with why it matches your interests / tracked files, plus "
                "facets and a featured list."))
async def list_news(
    my_interests: bool = Query(False),
    my_files: bool = Query(False),
    institution: Optional[str] = Query(None),
    commission_dg: Optional[str] = Query(None),
    item_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        interests = set(_interest_list(current_user)) if current_user else set()
        dgs = dgs_for_interests(interests)
        keywords = sorted(keywords_for_interests(interests))
        tracked = tracked_anchors(db, str(current_user.id)) if current_user else {}
        tracked_pa = tracked.get("policy_areas", set())

        q = db.query(EuNewsItem)

        # Soft register: Policy Interests, via the shared builder (policy_areas primary).
        if my_interests and interests:
            sql, params = build_pi_clause(interests, NEWS_SPEC, pfx="pi")
            if sql != "TRUE":
                q = q.filter(text(sql).bindparams(**params))

        # Hard register: My Tracked Files lens (topical overlap with tracked files).
        if my_files and tracked_pa:
            q = q.filter(text("policy_areas::text[] && ARRAY[" +
                              ", ".join(f":tf_{i}" for i in range(len(tracked_pa))) +
                              "]::text[]").bindparams(**{f"tf_{i}": pa for i, pa in enumerate(sorted(tracked_pa))}))

        if institution:
            q = q.filter(EuNewsItem.institution == institution)
        if commission_dg:
            q = q.filter(EuNewsItem.commission_dg == commission_dg)
        if item_type:
            q = q.filter(EuNewsItem.item_type == item_type)
        if search:
            q = q.filter(or_(EuNewsItem.title.ilike(f"%{search}%"),
                             EuNewsItem.summary.ilike(f"%{search}%")))

        total = q.count()
        rows = (q.order_by(EuNewsItem.news_date.desc().nullslast())
                .offset(offset).limit(limit).all())
        # Defensive: collapse rows sharing a canonical article URL (cross-listed).
        seen: set = set()
        uniq = []
        for e in rows:
            key = e.source_url or str(e.id)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(e)
        items = [_item_dict(e, interests, dgs, keywords, tracked_pa) for e in uniq]

        # Featured: most recent items with an image, PI-matching first.
        featured = [i for i in items if i["image_url"]]
        featured = sorted(featured, key=lambda i: (i["matches_interests"], i["news_date"] or ""), reverse=True)[:5]

        dg_counts = dict(db.query(EuNewsItem.commission_dg, func.count(EuNewsItem.id))
                         .filter(EuNewsItem.commission_dg.isnot(None))
                         .group_by(EuNewsItem.commission_dg).all())
        type_counts = dict(db.query(EuNewsItem.item_type, func.count(EuNewsItem.id))
                           .group_by(EuNewsItem.item_type).all())
        inst_counts = dict(db.query(EuNewsItem.institution, func.count(EuNewsItem.id))
                           .filter(EuNewsItem.institution.isnot(None))
                           .group_by(EuNewsItem.institution).all())

        return {
            "items": items,
            "featured": featured,
            "total": total,
            "pi_active": bool(my_interests and interests),
            "files_active": bool(my_files and tracked_pa),
            "has_tracked_files": bool(tracked_pa),
            "facets": {
                "institution": {k: int(v) for k, v in sorted(inst_counts.items(), key=lambda kv: -kv[1])},
                "commission_dg": {k: int(v) for k, v in sorted(dg_counts.items(), key=lambda kv: -kv[1])},
                "item_type": {k or "other": int(v) for k, v in type_counts.items()},
            },
        }
    except Exception as e:
        logger.exception(f"news list failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load news")


@router.get("/my-keywords", summary="My Policy-Interest keywords",
            description="Lowercase topic keywords from the user's Policy Interests, "
                        "used to flag news that matches their interests.")
async def my_keywords(current_user: Optional[User] = Depends(get_current_user_optional)):
    interests = _interest_list(current_user) if current_user else []
    return {"keywords": sorted(keywords_for_interests(interests)), "dgs": sorted(dgs_for_interests(interests))}
