"""
MEP Watch API (MEUB Section 3) - a people-centric lens on the MEPs shaping the
user's files.

Stitches together what Brubru now holds per MEP (starting with the parliamentary
questions they tabled, enriched with author ids) to answer: "which MEPs are most
active on my policy interests, and what are they asking?" Each MEP card carries the
working EP profile link (built from the author id) the doceo pages hide. Read:
Yellow+. No Anthropic.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.w4_entities import ParliamentaryQuestion
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import keywords_for_interests
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mep-watch", tags=["MEP Watch"])

_MEP_BASE = "https://www.europarl.europa.eu/meps/en"


def _require_yellow(user: User):
    if not user or user.subscription_tier == "white":
        raise HTTPException(status_code=403, detail="MEP Watch requires Yellow or Blue tier.")


def _profile_url(mep_id: Optional[str], name: Optional[str]) -> Optional[str]:
    if not mep_id:
        return None
    slug = re.sub(r"\s+", "_", (name or "").strip().upper()) or "MEP"
    return f"{_MEP_BASE}/{mep_id}/{slug}/home"


def _pi_filter(q, user: User):
    """Restrict questions to the user's PI keywords (subject + text). (query, active)."""
    kws = keywords_for_interests(_interest_list(user))
    if not kws:
        return q, False
    clauses = []
    for kw in kws:
        like = f"%{kw}%"
        clauses.append(ParliamentaryQuestion.subject.ilike(like))
        clauses.append(ParliamentaryQuestion.text_question.ilike(like))
    return q.filter(or_(*clauses)), True


@router.get("")
def list_meps(
    my_interests: bool = Query(True),
    search: Optional[str] = Query(None),
    limit: int = Query(40, ge=1, le=120),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """MEPs ranked by how many questions they tabled on the user's interests."""
    _require_yellow(user)
    q = db.query(ParliamentaryQuestion)
    pi_active = False
    if my_interests:
        q, pi_active = _pi_filter(q, user)
    if search:
        q = q.filter(ParliamentaryQuestion.subject.ilike(f"%{search}%"))
    # Bounded aggregation in Python (preserves name<->id pairing, which a GROUP BY
    # on the array column would lose).
    rows = q.order_by(ParliamentaryQuestion.submitted_date.desc().nullslast()).limit(4000).all()
    agg: dict = {}
    for r in rows:
        names = list(r.asking_mep_names or [])
        ids = list(r.asking_mep_ids or [])
        d = r.submitted_date.isoformat() if r.submitted_date else None
        for i, name in enumerate(names):
            if not name:
                continue
            mid = ids[i] if i < len(ids) else None
            a = agg.setdefault(name, {"id": None, "count": 0, "latest": None, "subjects": []})
            a["count"] += 1
            if mid and not a["id"]:
                a["id"] = mid
            if d and (not a["latest"] or d > a["latest"]):
                a["latest"] = d
            if len(a["subjects"]) < 3:
                a["subjects"].append(r.subject)
    meps = sorted(agg.items(), key=lambda kv: kv[1]["count"], reverse=True)[:limit]
    social = _latest_social(db, [a["id"] for _, a in meps if a["id"]])
    return {
        "pi_active": pi_active,
        "total_meps": len(agg),
        "items": [{
            "name": name,
            "mep_id": a["id"],
            "profile_url": _profile_url(a["id"], name),
            "question_count": a["count"],
            "latest_date": a["latest"],
            "sample_subjects": a["subjects"],
            # What the MEP SAID lately, from the social directory (Phase 4). A post is
            # a signal about a position, never the citable fact: the UI labels it as
            # social and unverified. Reposts are excluded -- an amplification is not
            # this MEP's statement (migration 219).
            "latest_social": social.get(str(a["id"]), []),
        } for name, a in meps],
    }


_LATEST_SOCIAL_DAYS = 14
_LATEST_SOCIAL_PER_MEP = 2


def _latest_social(db: Session, mep_ids: list) -> dict:
    """{mep_id: [{platform, posted_at, text, url}]} -- newest original posts, capped per MEP.

    social_accounts.entity_key holds the EP person id for entity_type='mep', the same id
    parliamentary_questions.asking_mep_ids carries, so the join needs no name matching.
    One query for the whole page; the window is short so the answer is fresh or empty.
    """
    if not mep_ids:
        return {}
    rows = db.execute(text("""
        SELECT a.entity_key, p.platform, p.posted_at, p.post_url,
               left(regexp_replace(coalesce(p.content, ''), '\\s+', ' ', 'g'), 220) AS txt
        FROM social_posts p
        JOIN social_accounts a ON a.id = p.account_id
        WHERE a.entity_type = 'mep'
          AND a.entity_key = ANY(:ids)
          AND NOT p.is_repost
          AND p.posted_at >= now() - make_interval(days => :days)
        ORDER BY a.entity_key, p.posted_at DESC
    """), {"ids": [str(i) for i in mep_ids], "days": _LATEST_SOCIAL_DAYS}).mappings().all()
    out: dict = {}
    for r in rows:
        bucket = out.setdefault(r["entity_key"], [])
        if len(bucket) >= _LATEST_SOCIAL_PER_MEP:
            continue
        bucket.append({
            "platform": r["platform"],
            "posted_at": r["posted_at"].isoformat() if r["posted_at"] else None,
            "text": r["txt"],
            "url": r["post_url"],
        })
    return out


@router.get("/questions")
def mep_questions(
    mep: str = Query(..., description="MEP name as it appears on questions"),
    my_interests: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """One MEP's tabled questions (optionally restricted to the user's interests)."""
    _require_yellow(user)
    q = db.query(ParliamentaryQuestion).filter(ParliamentaryQuestion.asking_mep_names.any(mep))
    if my_interests:
        q, _ = _pi_filter(q, user)
    rows = q.order_by(ParliamentaryQuestion.submitted_date.desc().nullslast()).limit(limit).all()
    mep_id = None
    for r in rows:
        names = list(r.asking_mep_names or [])
        ids = list(r.asking_mep_ids or [])
        if mep in names:
            i = names.index(mep)
            if i < len(ids) and ids[i]:
                mep_id = ids[i]
                break
    return {
        "mep": mep,
        "mep_id": mep_id,
        "profile_url": _profile_url(mep_id, mep),
        "total": len(rows),
        "questions": [{
            "reference": r.question_reference,
            "type": r.question_type.value if hasattr(r.question_type, "value") else r.question_type,
            "subject": r.subject,
            "submitted_date": r.submitted_date.isoformat() if r.submitted_date else None,
            "answered": bool(r.text_answer and len(r.text_answer.strip()) > 10),
            "source_url": r.source_url,
        } for r in rows],
    }
