"""
MEUB News API — EU institutional news, PI-filterable, image-rich.

Reads eu_news_items (migration 101). Powers the Section-3 "News" tab: a featured
hero + a card feed, filterable by the user's Policy Interests (commission_dg +
title/summary keyword) and by institution / DG / type.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.eu_news_item import EuNewsItem
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import dgs_for_interests, keywords_for_interests
from knowledge_base.eu_calendar_institutions import COMMISSION_DG_NAME
from .auth_optional import get_current_user_optional

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eu-news", tags=["EU News"])


def _user_keywords(user: Optional[User]) -> List[str]:
    return sorted(keywords_for_interests(_interest_list(user))) if user else []


def _user_dgs(user: Optional[User]) -> set:
    return dgs_for_interests(_interest_list(user)) if user else set()


def _pi_clause(dgs: set, keywords: List[str]):
    clauses = []
    if dgs:
        clauses.append(EuNewsItem.commission_dg.in_(list(dgs)))
    for kw in keywords:
        clauses.append(EuNewsItem.title.ilike(f"%{kw}%"))
        clauses.append(EuNewsItem.summary.ilike(f"%{kw}%"))
    return or_(*clauses) if clauses else None


def _matches(item: EuNewsItem, dgs: set, keywords: List[str]) -> bool:
    if item.commission_dg and item.commission_dg in dgs:
        return True
    hay = f"{item.title or ''} {item.summary or ''}".lower()
    return any(k in hay for k in keywords)


def _item_dict(e: EuNewsItem, dgs: set, keywords: List[str]) -> dict:
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
        "image_url": e.image_url,
        "source_url": e.source_url,
        "matches_interests": _matches(e, dgs, keywords),
    }


@router.get("/items", summary="EU institutional news feed",
            description=(
                "**What it does**\nReturns the aggregated EU institutional news feed "
                "(Commission hub + every DG/agency newsroom), image-rich and sorted "
                "newest-first, with a featured set for the hero.\n\n"
                "**When to use it**\nThe MEUB Section-3 'News' tab.\n\n"
                "**Input**\n`my_interests=true` to keep only news touching your Policy "
                "Interests; `institution`; `commission_dg`; `item_type`; `search`; "
                "`limit`/`offset`.\n\n"
                "**You get back**\nNews cards (title, summary, image, DG, date, link) + "
                "facets (by DG, by type) + a featured list."))
async def list_news(
    my_interests: bool = Query(False),
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
        dgs = _user_dgs(current_user)
        keywords = _user_keywords(current_user)

        q = db.query(EuNewsItem)
        if my_interests:
            clause = _pi_clause(dgs, keywords)
            if clause is not None:
                q = q.filter(clause)
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
        # Defensive: collapse any rows sharing a canonical article URL (the same
        # article can be cross-listed on several DG pages).
        seen: set = set()
        uniq = []
        for e in rows:
            key = e.source_url or str(e.id)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(e)
        items = [_item_dict(e, dgs, keywords) for e in uniq]

        # Featured: the most recent items that have an image (PI-matching first).
        featured = [i for i in items if i["image_url"]]
        featured.sort(key=lambda i: (not i["matches_interests"], i["news_date"] or ""), reverse=False)
        featured = sorted(featured, key=lambda i: (i["matches_interests"], i["news_date"] or ""), reverse=True)[:5]

        # Facets over the whole table for the filter UI.
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
            "pi_active": bool(my_interests and (dgs or keywords)),
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
    return {"keywords": _user_keywords(current_user), "dgs": sorted(_user_dgs(current_user))}
