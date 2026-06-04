"""
Position Analysis API.

Endpoints:
  GET  /api/positions/{carriage_id}              -- full position snapshot
  GET  /api/positions/{carriage_id}/amendments    -- article-by-article drill-down
  PATCH /api/positions/{carriage_id}/user-position -- save the user's stance on a tracked file
  POST /api/positions/{carriage_id}/refresh        -- force re-aggregation (Blue tier)
  GET  /api/positions/                            -- list tracked files with position summary

All endpoints require authentication. Writes of user_position require that
the user tracks the carriage (row in user_carriage_tracks).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.auth import get_current_user
from core.database import get_db
from models.file_position import FilePositionSnapshot
from models.legislative_train import LegislativeCarriage, UserCarriageTrack
from models.user import User
from services.positions import get_position_aggregator
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import (
    committees_for_interests, keywords_for_interests,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/positions", tags=["Position Analysis"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class PositionResponse(BaseModel):
    carriage_id: UUID
    procedure_ref: str
    title: Optional[str] = None
    data_completeness: str
    confidence: str
    commission_position: Dict[str, Any]
    parliament_position: Dict[str, Any]
    council_position: Dict[str, Any]
    sources: Dict[str, Any] = Field(default_factory=dict)
    user_position: Optional[Dict[str, Any]] = None
    is_tracked: bool = False
    generated_at: Optional[datetime] = None


class AmendmentDrilldownResponse(BaseModel):
    carriage_id: UUID
    procedure_ref: str
    articles: List[Dict[str, Any]]


class UserPositionPayload(BaseModel):
    stance: str = Field(..., description="support | support_with_amendments | oppose | neutral | undecided")
    notes: Optional[str] = None
    evidence_urls: Optional[List[str]] = None
    priority_articles: Optional[List[str]] = None


class PositionListItem(BaseModel):
    carriage_id: UUID
    procedure_ref: Optional[str] = None
    title: Optional[str] = None
    lead_committee: Optional[str] = None
    current_status: Optional[str] = None
    is_tracked: bool = False
    is_recently_updated: bool = False
    is_pi_match: bool = False
    user_stance: Optional[str] = None
    has_snapshot: bool = False


class PositionListResponse(BaseModel):
    pi_active: bool = False
    tracked: List[PositionListItem] = Field(default_factory=list)
    suggested: List[PositionListItem] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _snapshot_to_response(
    carriage: LegislativeCarriage,
    snap: FilePositionSnapshot,
    track: Optional[UserCarriageTrack],
) -> PositionResponse:
    return PositionResponse(
        carriage_id=carriage.id,
        procedure_ref=snap.procedure_ref,
        title=carriage.title,
        data_completeness=snap.data_completeness or "partial",
        confidence=snap.confidence or "medium",
        commission_position=snap.commission_position or {},
        parliament_position=snap.parliament_position or {},
        council_position=snap.council_position or {},
        sources=snap.sources or {},
        user_position=(track.user_position if track else None),
        is_tracked=track is not None,
        generated_at=snap.generated_at,
    )


async def _ensure_snapshot(
    carriage: LegislativeCarriage, db: Session, force: bool = False
) -> FilePositionSnapshot:
    agg = get_position_aggregator(db=db)
    snap = agg.get_cached(carriage.id)
    if snap and agg.is_fresh(snap) and not force:
        return snap
    await agg.aggregate_and_cache(carriage)
    return agg.get_cached(carriage.id)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

def _carriage_to_item(c: LegislativeCarriage, *, is_tracked: bool, is_pi_match: bool,
                      user_stance: Optional[str], has_snapshot: bool) -> PositionListItem:
    return PositionListItem(
        carriage_id=c.id,
        procedure_ref=c.oeil_procedure_ref or c.file_id,
        title=c.title,
        lead_committee=c.lead_committee,
        current_status=c.current_status,
        is_tracked=is_tracked,
        is_recently_updated=bool(c.is_recently_updated),
        is_pi_match=is_pi_match,
        user_stance=user_stance,
        has_snapshot=has_snapshot,
    )


@router.get("/", response_model=PositionListResponse, summary="List files with positions: tracked + suggested for your interests")
async def list_positions(
    my_interests: bool = Query(True),
    limit: int = Query(40, ge=1, le=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PositionListResponse:
    """Lightweight list (no snapshot generation): the user's TRACKED files, plus -
    when my_interests is on - files SUGGESTED by the PI crosswalk (lead committee or a
    PI keyword in the title). Snapshots are generated on demand when a file is opened."""
    # Tracked files
    tracks = (db.query(UserCarriageTrack)
              .filter(UserCarriageTrack.user_id == current_user.id).all())
    track_by_carriage = {t.carriage_id: t for t in tracks}
    tracked_ids = list(track_by_carriage.keys())

    tracked_carriages = (db.query(LegislativeCarriage)
                         .filter(LegislativeCarriage.id.in_(tracked_ids)).all()) if tracked_ids else []

    # PI-suggested files (excluding already-tracked)
    pi_active = False
    suggested_carriages: List[LegislativeCarriage] = []
    if my_interests:
        interests = _interest_list(current_user)
        if interests:
            committees = committees_for_interests(interests)
            keywords = keywords_for_interests(interests)
            clauses = []
            if committees:
                clauses.append(LegislativeCarriage.lead_committee.in_(list(committees)))
            for kw in list(keywords)[:40]:
                clauses.append(LegislativeCarriage.title.ilike(f"%{kw}%"))
            if clauses:
                pi_active = True
                q = db.query(LegislativeCarriage).filter(or_(*clauses))
                if tracked_ids:
                    q = q.filter(~LegislativeCarriage.id.in_(tracked_ids))
                suggested_carriages = (q.order_by(LegislativeCarriage.last_updated.desc().nullslast())
                                       .limit(limit).all())

    # Which of these already have a cached snapshot (cheap single query)
    all_ids = [c.id for c in tracked_carriages] + [c.id for c in suggested_carriages]
    snap_ids = set()
    if all_ids:
        snap_ids = {r[0] for r in db.query(FilePositionSnapshot.carriage_id)
                    .filter(FilePositionSnapshot.carriage_id.in_(all_ids)).all()}

    tracked = [
        _carriage_to_item(
            c, is_tracked=True, is_pi_match=False,
            user_stance=((track_by_carriage[c.id].user_position or {}).get("stance")
                         if track_by_carriage[c.id].user_position else None),
            has_snapshot=c.id in snap_ids)
        for c in tracked_carriages
    ]
    suggested = [
        _carriage_to_item(c, is_tracked=False, is_pi_match=True,
                          user_stance=None, has_snapshot=c.id in snap_ids)
        for c in suggested_carriages
    ]
    return PositionListResponse(pi_active=pi_active, tracked=tracked, suggested=suggested)


@router.get("/{carriage_id}", response_model=PositionResponse, summary="Full position snapshot for a legislative file")
async def get_position(
    carriage_id: UUID,
    refresh: bool = Query(False, description="Force re-aggregation"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PositionResponse:
    carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == carriage_id).first()
    if not carriage:
        raise HTTPException(status_code=404, detail="Legislative file not found")
    if refresh and current_user.subscription_tier not in ("blue", "admin"):
        raise HTTPException(status_code=403, detail="Blue subscription required for forced refresh")
    try:
        snap = await _ensure_snapshot(carriage, db, force=refresh)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[positions] aggregation failed for %s: %s", carriage_id, exc)
        raise HTTPException(status_code=500, detail=f"Position aggregation failed: {exc}")
    if not snap:
        raise HTTPException(status_code=500, detail="Snapshot not available")
    track = (
        db.query(UserCarriageTrack)
        .filter(UserCarriageTrack.user_id == current_user.id, UserCarriageTrack.carriage_id == carriage.id)
        .first()
    )
    return _snapshot_to_response(carriage, snap, track)


@router.get("/{carriage_id}/amendments", response_model=AmendmentDrilldownResponse, summary="Article-by-article drill-down")
async def get_amendment_drilldown(
    carriage_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AmendmentDrilldownResponse:
    carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == carriage_id).first()
    if not carriage:
        raise HTTPException(status_code=404, detail="Legislative file not found")
    snap = await _ensure_snapshot(carriage, db)
    return AmendmentDrilldownResponse(
        carriage_id=carriage.id,
        procedure_ref=snap.procedure_ref,
        articles=snap.amendment_positions or [],
    )


VALID_STANCES = {"support", "support_with_amendments", "oppose", "neutral", "undecided"}


@router.patch("/{carriage_id}/user-position", response_model=PositionResponse, summary="Save user's position on a tracked file")
async def upsert_user_position(
    carriage_id: UUID,
    payload: UserPositionPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PositionResponse:
    if payload.stance not in VALID_STANCES:
        raise HTTPException(
            status_code=422,
            detail=f"stance must be one of: {sorted(VALID_STANCES)}",
        )
    carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == carriage_id).first()
    if not carriage:
        raise HTTPException(status_code=404, detail="Legislative file not found")

    track = (
        db.query(UserCarriageTrack)
        .filter(UserCarriageTrack.user_id == current_user.id, UserCarriageTrack.carriage_id == carriage.id)
        .first()
    )
    if track is None:
        # auto-track when setting a position
        track = UserCarriageTrack(user_id=current_user.id, carriage_id=carriage.id)
        db.add(track)

    track.user_position = {
        "stance": payload.stance,
        "notes": payload.notes,
        "evidence_urls": payload.evidence_urls or [],
        "priority_articles": payload.priority_articles or [],
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    db.commit()

    snap = await _ensure_snapshot(carriage, db)
    return _snapshot_to_response(carriage, snap, track)


@router.get("/{carriage_id}/lobbying", summary="Who is lobbying this file (EP rapporteur/shadow meetings)")
async def get_lobbying(
    carriage_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tier-0 lobbying footprint for this dossier: the interest representatives who met
    its rapporteur/shadows (from mep_lobby_meetings, by procedure_ref), grouped by org
    with access depth. Factual footprint only - no success/causation is implied."""
    from models.mep_lobby_meeting import MepLobbyMeeting as MLM
    from api.lobby_meetings import _ep_access, _ACCESS_RANK, _ACCESS_LABEL

    carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == carriage_id).first()
    if not carriage:
        raise HTTPException(status_code=404, detail="Legislative file not found")
    ref = carriage.oeil_procedure_ref
    if not ref:
        return {"procedure_ref": None, "total": 0, "organisations": []}

    rows = db.query(MLM).filter(MLM.procedure_ref == ref).all()
    orgs: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        key = r.organisation_norm or (r.organisation or "").lower()
        if not key:
            continue
        o = orgs.setdefault(key, {
            "organisation": r.organisation, "website": r.org_website,
            "register_url": r.org_register_url, "transparency_register_id": r.transparency_register_id,
            "meetings": 0, "reached_rapporteur": False, "best_access": 0, "best_label": None,
            "meps": set(), "first_meeting": None, "last_meeting": None,
        })
        o["meetings"] += 1
        if r.mep_name:
            o["meps"].add(r.mep_name)
        if r.meeting_date:
            d = r.meeting_date.isoformat()
            o["first_meeting"] = min(o["first_meeting"], d) if o["first_meeting"] else d
            o["last_meeting"] = max(o["last_meeting"], d) if o["last_meeting"] else d
        level, staff = _ep_access(r.role)
        if not staff and _ACCESS_RANK[level] > o["best_access"]:
            o["best_access"] = _ACCESS_RANK[level]
            o["best_label"] = _ACCESS_LABEL[level]
        if not staff and level == "rapporteur":
            o["reached_rapporteur"] = True

    out = sorted(
        [{**{k: v for k, v in o.items() if k != "meps"}, "meps": sorted(o["meps"])} for o in orgs.values()],
        key=lambda x: (x["reached_rapporteur"], x["best_access"], x["meetings"]), reverse=True)

    # File outcome (factual): the actual EP roll-call + the procedure status. This lets
    # the UI set engagement against the outcome WITHOUT inferring causation. A true
    # "did the org get what it wanted" read needs the org's stated position (positions layer).
    from sqlalchemy import text as _t
    vote = db.execute(_t("""
        SELECT result, vote_date, level FROM ep_roll_call_votes
        WHERE procedure_ref = :p ORDER BY (CASE WHEN level='plenary' THEN 0 ELSE 1 END), vote_date DESC NULLS LAST
        LIMIT 1"""), {"p": ref}).fetchone()
    outcome = {
        "status": carriage.current_status,
        "has_vote": bool(vote),
        "result": vote.result if vote else None,
        "vote_date": vote.vote_date.isoformat() if vote and vote.vote_date else None,
        "vote_level": vote.level if vote else None,
    }
    return {"procedure_ref": ref, "total": len(rows), "organisations": out, "outcome": outcome}


@router.get("/{carriage_id}/alignment", summary="Tier-1 outcome alignment: lobbying orgs' stated consultation positions vs the file outcome")
async def get_alignment(
    carriage_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """For the organisations that lobbied this file's rapporteur/shadows, surface their
    STATED positions from EC Have-Your-Say consultations (matched by Transparency Register
    id), set against the file outcome. Org-anchored (Option A): positions are what the org
    told the Commission in named consultations - NOT necessarily on this exact dossier, and
    NEVER a causal claim. Coverage is partial by design."""
    from models.mep_lobby_meeting import MepLobbyMeeting as MLM
    from models.consultation_feedback import ConsultationFeedback as CF
    from api.lobby_meetings import _ep_access, _ACCESS_RANK

    carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == carriage_id).first()
    if not carriage:
        raise HTTPException(status_code=404, detail="Legislative file not found")
    ref = carriage.oeil_procedure_ref
    if not ref:
        return {"procedure_ref": None, "organisations": [], "coverage": {"lobbying_orgs": 0, "with_position": 0}}

    # The file's lobbying orgs (by register id + normalised name), with access depth.
    lobby_rows = db.query(MLM).filter(MLM.procedure_ref == ref).all()
    orgs: Dict[str, Dict[str, Any]] = {}
    tr_ids, norms = set(), set()
    for r in lobby_rows:
        key = r.organisation_norm or (r.organisation or "").lower()
        if not key:
            continue
        o = orgs.setdefault(key, {
            "organisation": r.organisation, "organisation_norm": r.organisation_norm,
            "transparency_register_id": r.transparency_register_id, "meetings": 0,
            "reached_rapporteur": False, "best_access": 0,
        })
        o["meetings"] += 1
        if r.transparency_register_id:
            tr_ids.add(r.transparency_register_id)
        if r.organisation_norm:
            norms.add(r.organisation_norm)
        level, staff = _ep_access(r.role)
        if not staff and level == "rapporteur":
            o["reached_rapporteur"] = True

    # Captured consultation positions for those orgs (register id first, else normalised name).
    positions_by_key: Dict[str, list] = {}
    if tr_ids or norms:
        clauses = []
        if tr_ids:
            clauses.append(CF.transparency_register_id.in_(list(tr_ids)))
        if norms:
            clauses.append(CF.organisation_norm.in_(list(norms)))
        fb = db.query(CF).filter(or_(*clauses)).all()
        for f in fb:
            # attach to the matching lobbying org (by tr id, else norm)
            key = None
            for k, o in orgs.items():
                if (f.transparency_register_id and o["transparency_register_id"] == f.transparency_register_id) \
                   or (f.organisation_norm and o["organisation_norm"] == f.organisation_norm):
                    key = k
                    break
            if key is None:
                continue
            if f.stance == "attachment_only":
                continue   # no inline text -> nothing to show
            positions_by_key.setdefault(key, []).append({
                "stance": f.stance, "summary": f.stance_summary,
                "excerpt": f.feedback_excerpt,
                "consultation_title": f.consultation_title, "dg": f.dg_responsible,
                "source_url": f.source_url, "date": f.feedback_date.isoformat() if f.feedback_date else None,
            })

    # File outcome (factual).
    from sqlalchemy import text as _t
    vote = db.execute(_t("""
        SELECT result, vote_date, level FROM ep_roll_call_votes
        WHERE procedure_ref = :p ORDER BY (CASE WHEN level='plenary' THEN 0 ELSE 1 END), vote_date DESC NULLS LAST
        LIMIT 1"""), {"p": ref}).fetchone()
    outcome = {
        "status": carriage.current_status, "has_vote": bool(vote),
        "result": vote.result if vote else None,
        "vote_date": vote.vote_date.isoformat() if vote and vote.vote_date else None,
        "vote_level": vote.level if vote else None,
    }

    # Orgs WITH a captured position first, ranked by access depth + meetings.
    out = []
    for k, o in orgs.items():
        pos = positions_by_key.get(k, [])   # any filed feedback with inline text (stance may be pending)
        out.append({
            "organisation": o["organisation"],
            "transparency_register_id": o["transparency_register_id"],
            "meetings": o["meetings"], "reached_rapporteur": o["reached_rapporteur"],
            "positions": pos, "has_position": bool(pos),
        })
    out.sort(key=lambda x: (x["has_position"], x["reached_rapporteur"], x["meetings"]), reverse=True)

    with_position = sum(1 for o in out if o["has_position"])
    return {
        "procedure_ref": ref,
        "outcome": outcome,
        "coverage": {"lobbying_orgs": len(out), "with_position": with_position},
        "organisations": out,
    }


@router.get("/{carriage_id}/actual-vote", summary="Actual roll-call result vs prediction")
async def get_actual_vote(
    carriage_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The actual EP roll-call outcome for this file (plenary preferred, else committee),
    so the predicted group stances can be shown against what really happened."""
    from sqlalchemy import text as _t
    rows = db.execute(_t("""
        SELECT level, result, votes_for, votes_against, votes_abstention, group_breakdown,
               vote_date, ta_reference, title, source_url, committee_code
        FROM ep_roll_call_votes
        WHERE carriage_id = :cid
        ORDER BY (CASE WHEN level='plenary' THEN 0 ELSE 1 END), vote_date DESC NULLS LAST
        LIMIT 1
    """), {"cid": str(carriage_id)}).fetchall()
    if not rows:
        return {"has_vote": False}
    r = rows[0]
    return {
        "has_vote": True,
        "level": r.level,
        "result": r.result,
        "votes_for": r.votes_for, "votes_against": r.votes_against, "votes_abstention": r.votes_abstention,
        "group_breakdown": r.group_breakdown or {},
        "vote_date": r.vote_date.isoformat() if r.vote_date else None,
        "ta_reference": r.ta_reference,
        "title": r.title,
        "source_url": r.source_url,
        "committee_code": r.committee_code,
    }


@router.post("/{carriage_id}/refresh", response_model=PositionResponse, summary="Force-refresh the position snapshot (Blue tier)")
async def force_refresh(
    carriage_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PositionResponse:
    if current_user.subscription_tier not in ("blue", "admin"):
        raise HTTPException(status_code=403, detail="Blue subscription required")
    carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == carriage_id).first()
    if not carriage:
        raise HTTPException(status_code=404, detail="Legislative file not found")
    snap = await _ensure_snapshot(carriage, db, force=True)
    track = (
        db.query(UserCarriageTrack)
        .filter(UserCarriageTrack.user_id == current_user.id, UserCarriageTrack.carriage_id == carriage.id)
        .first()
    )
    return _snapshot_to_response(carriage, snap, track)
