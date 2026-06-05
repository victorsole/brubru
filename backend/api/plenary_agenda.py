"""
EP Plenary - Order of Business API (MEUB Section 3).

The plenary, through the PI lens: the upcoming sitting schedule + the dossiers
plenary has recently adopted on the user's topics (with procedure ref + lead
committee), plus a pointer to the plenary roll-call votes. Read: Yellow+.

NOTE: the forthcoming item-level Order of Business lives in the doceo synoptic OJ
(WAF-walled); wiring that live parse is a planned enhancement. Until then this
surfaces the reliable structured signals: the calendar schedule + adopted-text
record (which is what plenary worked on) + the Votes tab.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text as sqla_text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.eu_calendar import EUCalendarEvent
from models.ep_vote import EpVote
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.tracked_lens import tracked_anchors
from services.tracking.pi_committee_crosswalk import (
    committees_for_interests, keywords_for_interests,
)
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plenary-agenda", tags=["EP Plenary Order of Business"])


def _require_yellow(user: User):
    if not user or user.subscription_tier == "white":
        raise HTTPException(status_code=403, detail="Plenary Order of Business requires Yellow or Blue tier.")


@router.get("")
def plenary_order_of_business(
    my_interests: bool = Query(True),
    my_files: bool = Query(False),
    search: Optional[str] = Query(None),
    limit: int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upcoming plenary sittings + recently-adopted plenary business on the user's
    interests."""
    _require_yellow(user)
    today = date.today()
    _tracked = tracked_anchors(db, str(user.id)) if user else {}
    tracked_procs = _tracked.get("procedures", set())
    tracked_committees = _tracked.get("committees", set())

    # 1) Upcoming sittings (the schedule)
    sess_rows = (
        db.query(EUCalendarEvent)
        .filter(EUCalendarEvent.event_type == "plenary_session",
                EUCalendarEvent.institution == "EP",
                EUCalendarEvent.start_date >= today)
        .order_by(EUCalendarEvent.start_date).limit(10).all()
    )
    sessions = [{
        "date": r.start_date.isoformat() if r.start_date else None,
        "end_date": r.end_date.isoformat() if r.end_date else None,
        "title": r.title,
        "agenda_url": r.agenda_url or r.source_url,
    } for r in sess_rows]

    # 2) Recently adopted plenary business (texts_adopted), PI-filtered.
    interests = _interest_list(user)
    committees = committees_for_interests(interests) if interests else set()
    kws = keywords_for_interests(interests) if interests else set()
    sql = ["SELECT ta_reference, title, procedure_ref, committees, adoption_date, source_url",
           "FROM texts_adopted WHERE adoption_date IS NOT NULL"]
    params: dict = {}
    pi_active = False
    if my_interests and (committees or kws):
        conds = []
        if committees:
            conds.append("committees && CAST(:coms AS varchar[])")
            params["coms"] = list(committees)
        for i, kw in enumerate(kws):
            conds.append(f"title ILIKE :kw{i}")
            params[f"kw{i}"] = f"%{kw}%"
        if conds:
            sql.append("AND (" + " OR ".join(conds) + ")")
            pi_active = True
    if my_files and (tracked_procs or tracked_committees):
        fconds = []
        if tracked_procs:
            fconds.append("procedure_ref = ANY(:tprocs)")
            params["tprocs"] = list(tracked_procs)
        if tracked_committees:
            fconds.append("committees && CAST(:tcoms AS varchar[])")
            params["tcoms"] = list(tracked_committees)
        sql.append("AND (" + " OR ".join(fconds) + ")")
    if search:
        sql.append("AND title ILIKE :search")
        params["search"] = f"%{search}%"
    sql.append("ORDER BY adoption_date DESC LIMIT :lim")
    params["lim"] = limit
    rows = db.execute(sqla_text(" ".join(sql)), params).mappings().all()
    def _doc_url(src):
        # The stored doceo URL is canonical (e.g. TA-10-2026-0189_EN.pdf). Prefer the
        # readable HTML page; both resolve on europarl.europa.eu. Never reconstruct
        # from ta_reference (that produced broken links).
        if not src:
            return None
        return src[:-4] + ".html" if src.endswith(".pdf") else src

    def _oeil(ref):
        return (f"https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={ref}"
                if ref else None)

    business = [{
        "ta_reference": r["ta_reference"],
        "title": r["title"],
        "procedure_ref": r["procedure_ref"],
        "committees": list(r["committees"] or []),
        "adoption_date": r["adoption_date"].isoformat() if r["adoption_date"] else None,
        "document_url": _doc_url(r["source_url"]),
        "oeil_url": _oeil(r["procedure_ref"]),
        "matches_tracked": bool((r["procedure_ref"] and r["procedure_ref"] in tracked_procs)
                                or (set(r["committees"] or []) & tracked_committees)),
    } for r in rows]

    plenary_votes = db.query(EpVote.id).filter(EpVote.level == "plenary").count()

    return {
        "pi_active": pi_active,
        "files_active": bool(my_files and (tracked_procs or tracked_committees)),
        "has_tracked_files": bool(tracked_procs or tracked_committees),
        "sessions": sessions,
        "business": business,
        "business_total": len(business),
        "plenary_votes": plenary_votes,
    }
