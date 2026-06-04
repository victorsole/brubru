"""
My OJ API — the day's Official Journal entries, filterable by Policy Interests.

Reads ``oj_entries`` (migration 099). Powers the MEUB "My OJ" tab: a date
selector, day-at-a-glance facets, act cards, the PI lens (title-keyword match on
the user's Policy Interests, like the Legislative Train view), and the bridge to
My Tracked Files (an act carries its matched carriage when the CELEX lines up).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.oj_entry import OjEntry
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import keywords_for_interests
from .auth_optional import get_current_user_optional

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oj", tags=["My OJ"])


def _user_keywords(user: Optional[User]) -> List[str]:
    if not user:
        return []
    return sorted(keywords_for_interests(_interest_list(user)))


def _matches(entry: OjEntry, keywords: List[str]) -> bool:
    if not keywords:
        return False
    hay = (entry.title or "").lower()
    return any(k in hay for k in keywords)


def _entry_dict(e: OjEntry, keywords: List[str]) -> dict:
    return {
        "id": str(e.id),
        "oj_date": e.oj_date.isoformat() if e.oj_date else None,
        "series": e.series,
        "oj_number": e.oj_number,
        "oj_id": e.oj_id,
        "celex": e.celex,
        "title": e.title,
        "act_type": e.act_type,
        "category": e.category,
        "institution": e.institution,
        "eurlex_url": e.eurlex_url,
        "plain_explanation": e.plain_explanation,
        "change_kind": e.change_kind,
        "theme": e.theme,
        "carriage_id": str(e.carriage_id) if e.carriage_id else None,
        "matched_procedure_ref": e.matched_procedure_ref,
        "matched_ta_reference": e.matched_ta_reference,
        "is_tracked": e.carriage_id is not None,
        "matches_interests": _matches(e, keywords),
    }


@router.get("/dates", summary="Available OJ dates",
            description="The OJ publication dates Brubru has ingested, newest first. "
                        "The 'My OJ' tab defaults to the latest.")
async def oj_dates(db: Session = Depends(get_db)):
    rows = (db.query(OjEntry.oj_date, func.count(OjEntry.id))
            .group_by(OjEntry.oj_date).order_by(OjEntry.oj_date.desc()).all())
    return {"dates": [{"date": d.isoformat(), "count": int(n)} for d, n in rows if d]}


@router.get("/entries", summary="OJ entries for a day",
            description=(
                "**What it does**\nReturns the Official Journal acts for a given day, "
                "grouped-ready, with the act type, institution, a EUR-Lex link, and a "
                "link back to My Tracked Files when the act matches a tracked dossier.\n\n"
                "**When to use it**\nThe MEUB 'My OJ' tab.\n\n"
                "**Input**\n`date` (YYYY-MM-DD; defaults to the latest); `series` (L|C); "
                "`my_interests=true` to keep only acts whose title matches your Policy "
                "Interests; `institution`; `act_type`; `search`.\n\n"
                "**You get back**\nThe acts plus day-at-a-glance facets (counts by "
                "series, type, institution)."))
async def oj_entries(
    date: Optional[str] = Query(None, description="YYYY-MM-DD; default = latest ingested"),
    series: Optional[str] = Query(None, description="L or C"),
    my_interests: bool = Query(False),
    institution: Optional[str] = Query(None),
    act_type: Optional[str] = Query(None),
    theme: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        keywords = _user_keywords(current_user)

        if date:
            target = date
        else:
            latest = db.query(func.max(OjEntry.oj_date)).scalar()
            target = latest.isoformat() if latest else None
        if not target:
            return {"date": None, "items": [], "facets": {}, "total": 0, "pi_active": False}

        q = db.query(OjEntry).filter(OjEntry.oj_date == target)
        if series:
            q = q.filter(OjEntry.series == series.upper())
        if institution:
            q = q.filter(OjEntry.institution == institution)
        if act_type:
            q = q.filter(OjEntry.act_type == act_type)
        if theme:
            q = q.filter(OjEntry.theme == theme)
        if search:
            q = q.filter(OjEntry.title.ilike(f"%{search}%"))

        rows = q.order_by(OjEntry.series, OjEntry.act_type, OjEntry.oj_number).all()
        items = [_entry_dict(e, keywords) for e in rows]
        if my_interests and keywords:
            items = [i for i in items if i["matches_interests"]]

        # Day-at-a-glance facets (computed over the unfiltered-by-my_interests set
        # for the chosen date, so the chips always reflect the whole day).
        all_day = db.query(OjEntry).filter(OjEntry.oj_date == target).all()
        def _count(attr):
            out = {}
            for e in all_day:
                k = getattr(e, attr) or "Other"
                out[k] = out.get(k, 0) + 1
            return dict(sorted(out.items(), key=lambda kv: -kv[1]))

        return {
            "date": target,
            "items": items,
            "total": len(items),
            "pi_active": bool(my_interests and keywords),
            "tracked_count": sum(1 for i in items if i["is_tracked"]),
            "interest_count": sum(1 for i in items if i["matches_interests"]),
            "facets": {
                "series": _count("series"),
                "act_type": _count("act_type"),
                "institution": _count("institution"),
                "theme": _count("theme"),
                "total": len(all_day),
            },
        }
    except Exception as e:
        logger.exception(f"oj entries failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load OJ entries")


@router.post("/explain/{entry_id}", summary="Explain an OJ act in plain language",
             description=(
                 "**What it does**\nReturns a one-sentence, jargon-free explanation of "
                 "an Official Journal act (the 'Explain with AI' button). Cached after "
                 "the first call.\n\n**When to use it**\nWhen a user clicks 'Explain with "
                 "AI' on an act with no explanation yet.\n\n**Input**\nThe entry id.\n\n"
                 "**You get back**\n`{explanation, available, cached}`. `available=false` "
                 "means the cost-capped provider (Mistral) is temporarily unreachable — "
                 "no Anthropic fallback is used."))
async def explain_entry(entry_id: str, db: Session = Depends(get_db)):
    try:
        e = db.query(OjEntry).filter(OjEntry.id == entry_id).first()
        if not e:
            raise HTTPException(status_code=404, detail="Entry not found")
        if e.plain_explanation:
            return {"explanation": e.plain_explanation, "available": True, "cached": True}

        from services.scrapers.oj_explainer import explain_batch
        result = await explain_batch([{"key": e.entry_key, "title": e.title}])
        text = result.get(e.entry_key)
        if text:
            e.plain_explanation = text
            db.commit()
            return {"explanation": text, "available": True, "cached": False}
        # Mistral unavailable (e.g. key 401) — graceful, no Anthropic fallback.
        return {"explanation": None, "available": False, "cached": False}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"oj explain failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to explain act")


@router.get("/my-keywords", summary="My Policy-Interest keywords",
            description="Lowercase topic keywords from the user's Policy Interests, "
                        "used to flag OJ acts that match their interests.")
async def my_keywords(current_user: Optional[User] = Depends(get_current_user_optional)):
    return {"keywords": _user_keywords(current_user)}
