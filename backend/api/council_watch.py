"""
Council Watch API (MEUB Section 3) - what the Council of the EU is doing on the
user's topics, through the shared Policy-Interest lens.

A unified timeline of Council activity: configuration MEETINGS (from the calendar,
PI-matched by Council configuration) + OUTCOMES / press (from the EU news feed,
PI-matched by keyword). Complements the Votes tab (how member states voted) and
My EU Calendar (when). Read: Yellow+. No Anthropic.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.eu_calendar import EUCalendarEvent
from models.eu_news_item import EuNewsItem
from models.ep_vote import EpVote
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import (
    council_configs_for_interests, keywords_for_interests,
)
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/council-watch", tags=["Council Watch"])

_COUNCIL_INST = ("COUNCIL", "EUROPEAN_COUNCIL")


def _require_yellow(user: User):
    if not user or user.subscription_tier == "white":
        raise HTTPException(status_code=403, detail="Council Watch requires Yellow or Blue tier.")


def _pi(user: User):
    interests = _interest_list(user)
    return (council_configs_for_interests(interests) if interests else set(),
            keywords_for_interests(interests) if interests else set())


def _meeting_items(db, user, my_interests, search) -> List[dict]:
    q = db.query(EUCalendarEvent).filter(EUCalendarEvent.institution.in_(_COUNCIL_INST))
    if my_interests:
        configs, kws = _pi(user)
        clauses = []
        if configs:
            clauses.append(EUCalendarEvent.council_configuration.in_(list(configs)))
        for kw in kws:
            clauses.append(EUCalendarEvent.title.ilike(f"%{kw}%"))
        if clauses:
            q = q.filter(or_(*clauses))
    if search:
        q = q.filter(EUCalendarEvent.title.ilike(f"%{search}%"))
    rows = q.order_by(EUCalendarEvent.start_date.desc()).limit(120).all()
    return [{
        "kind": "meeting",
        "date": r.start_date.isoformat() if r.start_date else None,
        "title": r.title,
        "configuration": r.council_configuration,
        "summary": r.description,
        "url": r.agenda_url or r.source_url,
        "institution": r.institution.value if hasattr(r.institution, "value") else r.institution,
    } for r in rows]


def _outcome_items(db, user, my_interests, search) -> List[dict]:
    q = db.query(EuNewsItem).filter(EuNewsItem.institution == "COUNCIL")
    if my_interests:
        _configs, kws = _pi(user)
        if kws:
            clauses = []
            for kw in kws:
                clauses.append(EuNewsItem.title.ilike(f"%{kw}%"))
                clauses.append(EuNewsItem.summary.ilike(f"%{kw}%"))
            q = q.filter(or_(*clauses))
    if search:
        q = q.filter(EuNewsItem.title.ilike(f"%{search}%"))
    rows = q.order_by(EuNewsItem.news_date.desc()).limit(80).all()
    return [{
        "kind": "outcome",
        "date": r.news_date.isoformat() if r.news_date else None,
        "title": r.title,
        "configuration": None,
        "summary": r.summary,
        "url": r.source_url,
        "image_url": r.image_url,
    } for r in rows]


@router.get("")
def list_activity(
    my_interests: bool = Query(True),
    kind: str = Query("all", description="all | meeting | outcome"),
    search: Optional[str] = Query(None),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Unified Council activity feed (meetings + outcomes), PI-filtered, newest first."""
    _require_yellow(user)
    items: List[dict] = []
    if kind in ("all", "meeting"):
        items += _meeting_items(db, user, my_interests, search)
    if kind in ("all", "outcome"):
        items += _outcome_items(db, user, my_interests, search)
    items.sort(key=lambda x: x["date"] or "", reverse=True)
    pi_active = my_interests and bool(any(_pi(user)))
    return {"total": len(items), "pi_active": pi_active,
            "items": items[offset:offset + limit]}


class SummariseRequest(BaseModel):
    title: str
    summary: Optional[str] = None
    kind: str = "meeting"
    configuration: Optional[str] = None
    lang: str = "en"


_SUM_CACHE: dict = {}  # content-hash -> summary (in-process)


@router.post("/summarise")
async def summarise(
    payload: SummariseRequest,
    user: User = Depends(get_current_user),
):
    """AI 'what this means' for a Council item, in the user's language. Qwen via HF
    (NO Anthropic). Cached in-process by content + language."""
    _require_yellow(user)
    from services.transcript_summary_service import LANG_NAMES
    lang = (payload.lang or "en").lower()
    lname = LANG_NAMES.get(lang, "English")
    import hashlib
    key = hashlib.md5(f"{payload.title}|{payload.summary}|{lang}".encode("utf-8")).hexdigest()
    if key in _SUM_CACHE:
        return {"summary": _SUM_CACHE[key], "lang": lang, "cached": True}

    kind = "meeting" if payload.kind == "meeting" else "outcome / press item"
    cfg = f" ({payload.configuration} configuration)" if payload.configuration else ""
    prompt = (
        f"This is a Council of the EU {kind}{cfg}. In 2-3 sentences, written in "
        f"{lname}, explain what it concerns and why it matters for an EU policy "
        "professional. Be concrete and factual; no preamble, no quotes.\n\n"
        f"Title: {payload.title}\n\nDetails: {(payload.summary or '')[:3000]}"
    )
    try:
        from services.ai.huggingface_service import get_huggingface_service
        out = await get_huggingface_service().chat_completion(
            model="Qwen/Qwen3-30B-A3B-Instruct-2507:featherless-ai",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=220, temperature=0.2,
        )
        out = (out or "").strip()
    except Exception as e:
        logger.warning("[council-watch] summarise failed: %s", e)
        out = None
    if not out:
        raise HTTPException(status_code=502, detail="Could not generate summary.")
    _SUM_CACHE[key] = out
    return {"summary": out, "lang": lang, "cached": False}


@router.get("/permreps")
def permreps(user: User = Depends(get_current_user)):
    """The 27 Member State Permanent Representations to the EU (+ Catalonia) - the
    member states' working level at the Council. Curated directory, links only."""
    _require_yellow(user)
    from knowledge_base.permanent_representations import PERMREPS
    return {"items": PERMREPS, "total": sum(1 for p in PERMREPS if not p.get("region"))}


@router.get("/stats")
def stats(
    my_interests: bool = Query(True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """KPIs for the Council Watch dashboard."""
    _require_yellow(user)
    configs, _kws = _pi(user)
    meetings = _meeting_items(db, user, my_interests, None)
    outcomes = _outcome_items(db, user, my_interests, None)
    today = date.today().isoformat()
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    upcoming = sum(1 for m in meetings if (m["date"] or "") >= today)
    recent_outcomes = sum(1 for o in outcomes if (o["date"] or "") >= cutoff)
    council_votes = db.query(func.count(EpVote.id)).filter(EpVote.level == "council").scalar() or 0
    # configurations present in the user's meeting set
    present_configs = sorted({m["configuration"] for m in meetings if m["configuration"]})
    return {
        "pi_active": my_interests and bool(configs),
        "upcoming_meetings": upcoming,
        "total_meetings": len(meetings),
        "recent_outcomes": recent_outcomes,
        "your_configurations": present_configs,
        "council_votes": int(council_votes),
    }
