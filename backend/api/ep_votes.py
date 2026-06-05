"""
EP Votes API — committee + plenary roll-call results for the MEUB "Votes" tab.

Reads the doceo-sourced roll-call store (``ep_roll_call_votes`` /
``ep_roll_call_records``, migration 098). Two tabs in the UI map to two
endpoints (``/committee`` and ``/plenary``); ``/procedure/{ref}`` returns both
levels for one dossier so the frontend can render the committee->plenary delta.

Everything is filterable by the signed-in user's Policy Interests (the PI lens
shared across MEUB): ``my_interests=true`` restricts to votes whose lead
committee is in the user's PI committee set.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.ep_vote import EpVote, EpVoteRecord
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import committees_for_interests
from services.tracking.tracked_lens import tracked_anchors, tracked_clause, TrackedSpec
from .auth_optional import get_current_user_optional

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ep-votes", tags=["EP Votes"])


# ---- helpers --------------------------------------------------------------

def _user_committees(user: Optional[User]) -> List[str]:
    if not user:
        return []
    return sorted(committees_for_interests(_interest_list(user)))


def _contestedness(v: EpVote) -> float:
    """0 = unanimous, ~1 = evenly split. min(for,against)/total — sort key for
    'votes that mattered'."""
    f, a, ab = (v.votes_for or 0), (v.votes_against or 0), (v.votes_abstention or 0)
    total = f + a + ab
    return (min(f, a) / total) if total else 0.0


def _margin(v: EpVote) -> int:
    return abs((v.votes_for or 0) - (v.votes_against or 0))


def _vote_summary(v: EpVote, my_committees: List[str], both_levels: set, tracked_procs: set) -> dict:
    return {
        "id": str(v.id),
        "level": v.level,
        "procedure_ref": v.procedure_ref,
        "matches_tracked": bool(v.procedure_ref and v.procedure_ref in tracked_procs),
        "carriage_id": str(v.carriage_id) if v.carriage_id else None,
        "report_ref": v.report_ref,
        "ta_reference": v.ta_reference,
        "title": v.title,
        "subject": v.subject,
        "committee_code": v.committee_code,
        "vote_date": v.vote_date.isoformat() if v.vote_date else None,
        "sitting_date": v.sitting_date.isoformat() if v.sitting_date else None,
        "item_number": v.item_number,
        "result": v.result,
        "votes_for": v.votes_for,
        "votes_against": v.votes_against,
        "votes_abstention": v.votes_abstention,
        "total_records": v.total_records,
        "vote_type": v.vote_type,
        "group_breakdown": v.group_breakdown or {},
        "country_breakdown": v.country_breakdown or {},
        "source_url": v.source_url,
        "matches_interests": bool(v.committee_code and v.committee_code in my_committees),
        "has_delta": v.procedure_ref in both_levels,
        "margin": _margin(v),
        "contestedness": round(_contestedness(v), 3),
    }


def _procedures_with_both_levels(db: Session) -> set:
    """OEIL refs that have BOTH a committee and a plenary vote (delta-eligible)."""
    rows = (
        db.query(EpVote.procedure_ref, EpVote.level)
        .filter(EpVote.procedure_ref.isnot(None))
        .distinct()
        .all()
    )
    seen: dict = {}
    for ref, level in rows:
        seen.setdefault(ref, set()).add(level)
    return {ref for ref, levels in seen.items() if {"committee", "plenary"} <= levels}


def _sort(items: List[dict], sort_by: str) -> List[dict]:
    if sort_by == "margin":          # closest first
        return sorted(items, key=lambda x: x["margin"])
    if sort_by == "dissent":         # most contested first
        return sorted(items, key=lambda x: x["contestedness"], reverse=True)
    if sort_by == "title":
        return sorted(items, key=lambda x: (x["title"] or "").lower())
    # default: most recent first
    return sorted(items, key=lambda x: (x["vote_date"] or ""), reverse=True)


# ---- list endpoints -------------------------------------------------------

def _list(level, db, user, my_interests, committees, search, sort_by, limit, offset, my_files=False):
    my_committees = _user_committees(user)
    both = _procedures_with_both_levels(db)
    tracked = tracked_anchors(db, str(user.id)) if user else {}
    tracked_procs = tracked.get("procedures", set())

    q = db.query(EpVote).filter(EpVote.level == level)

    filter_committees: List[str] = []
    if my_interests and my_committees:
        filter_committees = my_committees
    elif committees:
        filter_committees = [c.strip().upper() for c in committees.split(",") if c.strip()]
    if filter_committees:
        q = q.filter(EpVote.committee_code.in_(filter_committees))

    # My Tracked Files lens: votes on a procedure/committee the user tracks (hard).
    if my_files and tracked:
        tsql, tp = tracked_clause(tracked, TrackedSpec(procedure_col="procedure_ref",
                                                       committee_col="committee_code"))
        if tsql != "FALSE":
            q = q.filter(text(tsql).bindparams(**tp))

    if search:
        q = q.filter(EpVote.title.ilike(f"%{search}%"))

    total = q.count()
    rows = q.all()  # bounded set; sort/paginate in Python for margin/dissent keys
    items = [_vote_summary(v, my_committees, both, tracked_procs) for v in rows]
    items = _sort(items, sort_by)[offset:offset + limit]

    return {
        "items": items,
        "total": total,
        "level": level,
        "my_committees": my_committees,
        "pi_active": bool(my_interests and my_committees),
        "files_active": bool(my_files and tracked_procs),
        "has_tracked_files": bool(tracked_procs),
    }


@router.get("/committee", summary="Committee vote results",
            description=(
                "**What it does**\nLists European Parliament *committee* final-vote "
                "results (the responsible committee's roll-call on a report), with the "
                "tally, the per-group breakdown, and a link to the dossier.\n\n"
                "**When to use it**\nThe 'Committee results' tab of MEUB Votes.\n\n"
                "**Input**\n`my_interests=true` to restrict to your Policy-Interest "
                "committees; or `committees=AGRI,PECH`; `search`; "
                "`sort_by` in date|margin|dissent|title.\n\n"
                "**You get back**\nVote cards: outcome, for/against/abstentions, "
                "group breakdown, and whether a plenary delta is available."))
async def list_committee(
    my_interests: bool = Query(False),
    my_files: bool = Query(False),
    committees: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("date"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        return _list("committee", db, current_user, my_interests, committees, search, sort_by, limit, offset, my_files)
    except Exception as e:
        logger.exception(f"committee votes list failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list committee votes")


@router.get("/plenary", summary="Plenary vote results",
            description=(
                "**What it does**\nLists European Parliament *plenary* roll-call "
                "results (the whole-house final vote that adopts a text), with the "
                "tally, the per-group breakdown, and a link to the dossier.\n\n"
                "**When to use it**\nThe 'Plenary results' tab of MEUB Votes.\n\n"
                "**Input**\nSame filters as the committee endpoint.\n\n"
                "**You get back**\nVote cards with outcome + group breakdown; "
                "`has_delta=true` means a matching committee vote exists."))
async def list_plenary(
    my_interests: bool = Query(False),
    my_files: bool = Query(False),
    committees: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("date"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        return _list("plenary", db, current_user, my_interests, committees, search, sort_by, limit, offset, my_files)
    except Exception as e:
        logger.exception(f"plenary votes list failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list plenary votes")


@router.get("/council", summary="Council vote results",
            description=(
                "**What it does**\nLists Council of the EU *legislative* voting "
                "results (the member states' final vote that adopts an act), with the "
                "per-member-state breakdown and the qualified-majority figures.\n\n"
                "**When to use it**\nThe 'Council results' tab of MEUB Votes.\n\n"
                "**Input**\n`config=GAC,FAC` to filter by Council configuration; "
                "`search`; `sort_by` in date|margin|dissent|title.\n\n"
                "**You get back**\nVote cards: outcome, for/against/abstentions by "
                "member state, qualified-majority %, and a link to the source sheet. "
                "The per-country breakdown is auto-read from the Council's image-only "
                "result sheet (confidence flag + source link travel with each card)."))
async def list_council(
    config: Optional[str] = Query(None, description="Council configuration codes, e.g. GAC,FAC"),
    search: Optional[str] = Query(None),
    sort_by: str = Query("date"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        both: set = set()  # committee->plenary delta does not apply to Council
        q = db.query(EpVote).filter(EpVote.level == "council")
        if config:
            codes = [c.strip().upper() for c in config.split(",") if c.strip()]
            if codes:
                q = q.filter(EpVote.committee_code.in_(codes))
        if search:
            q = q.filter(EpVote.title.ilike(f"%{search}%"))
        total = q.count()
        rows = q.all()
        items = [_vote_summary(v, [], both) for v in rows]
        items = _sort(items, sort_by)[offset:offset + limit]
        # configuration facets for the filter chips
        configs = sorted({(v.committee_code or "").strip() for v in rows if v.committee_code})
        return {"items": items, "total": total, "level": "council", "configs": configs}
    except Exception as e:
        logger.exception(f"council votes list failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list council votes")


# ---- detail + delta -------------------------------------------------------

def _records_payload(db: Session, vote: EpVote) -> dict:
    recs = (
        db.query(EpVoteRecord)
        .filter(EpVoteRecord.vote_id == vote.id)
        .order_by(EpVoteRecord.political_group, EpVoteRecord.mep_name)
        .all()
    )
    return {
        "records": [
            {"mep_name": r.mep_name, "political_group": r.political_group,
             "country": r.country, "vote_choice": r.vote_choice, "is_intention": r.is_intention}
            for r in recs
        ],
    }


@router.get("/detail/{vote_id}", summary="Vote detail (per-MEP roll-call)",
            description=(
                "**What it does**\nFull detail for one vote: outcome, per-group "
                "breakdown, and the per-MEP roll-call (searchable in the UI).\n\n"
                "**When to use it**\nWhen a user opens a vote card.\n\n"
                "**Input**\nThe vote id.\n\n"
                "**You get back**\nThe vote summary plus every MEP's choice "
                "(+/-/0) and political group."))
async def vote_detail(
    vote_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        vote = db.query(EpVote).filter(EpVote.id == vote_id).first()
        if not vote:
            raise HTTPException(status_code=404, detail="Vote not found")
        my_committees = _user_committees(current_user)
        both = _procedures_with_both_levels(db)
        payload = _vote_summary(vote, my_committees, both)
        payload.update(_records_payload(db, vote))
        return payload
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"vote detail failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load vote detail")


@router.get("/procedure/{procedure_ref:path}", summary="Committee + plenary for a dossier (delta)",
            description=(
                "**What it does**\nReturns the committee vote and the plenary vote "
                "for one procedure side by side, plus the delta between them (did "
                "plenary confirm the committee? how did the margin move?).\n\n"
                "**When to use it**\nThe committee->plenary comparison module.\n\n"
                "**Input**\nThe OEIL procedure reference, e.g. `2025/0413(NLE)`.\n\n"
                "**You get back**\n`committee`, `plenary` (either may be null), and "
                "a `delta` summary when both exist."))
async def procedure_votes(
    procedure_ref: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        rows = db.query(EpVote).filter(EpVote.procedure_ref == procedure_ref).all()
        if not rows:
            raise HTTPException(status_code=404, detail="No votes for this procedure")
        my_committees = _user_committees(current_user)
        both = _procedures_with_both_levels(db)
        by_level = {r.level: r for r in rows}
        committee = by_level.get("committee")
        plenary = by_level.get("plenary")

        delta = None
        if committee and plenary:
            delta = {
                "confirmed": committee.result == plenary.result,
                "committee_result": committee.result,
                "plenary_result": plenary.result,
                "committee_margin": _margin(committee),
                "plenary_margin": _margin(plenary),
                "committee_tally": [committee.votes_for, committee.votes_against, committee.votes_abstention],
                "plenary_tally": [plenary.votes_for, plenary.votes_against, plenary.votes_abstention],
            }
        return {
            "procedure_ref": procedure_ref,
            "committee": _vote_summary(committee, my_committees, both) if committee else None,
            "plenary": _vote_summary(plenary, my_committees, both) if plenary else None,
            "delta": delta,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"procedure votes failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load procedure votes")


# ---- meta -----------------------------------------------------------------

@router.get("/my-committees", summary="My Policy-Interest committees",
            description="The signed-in user's PI committee codes — used to drive "
                        "the 'My interests' lens on the Votes tabs.")
async def my_committees(
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    return {"committees": _user_committees(current_user)}


@router.get("/stats", summary="Vote counts",
            description="Counts for the two tabs (committee / plenary) and how many "
                        "dossiers have a committee->plenary delta available.")
async def stats(db: Session = Depends(get_db)):
    try:
        by_level = dict(
            db.query(EpVote.level, func.count(EpVote.id)).group_by(EpVote.level).all()
        )
        return {
            "committee": int(by_level.get("committee", 0)),
            "plenary": int(by_level.get("plenary", 0)),
            "council": int(by_level.get("council", 0)),
            "with_delta": len(_procedures_with_both_levels(db)),
        }
    except Exception as e:
        logger.exception(f"vote stats failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load vote stats")
