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
from sqlalchemy.orm import Session

from api.auth import get_current_user
from core.database import get_db
from models.file_position import FilePositionSnapshot
from models.legislative_train import LegislativeCarriage, UserCarriageTrack
from models.user import User
from services.positions import get_position_aggregator

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


class TrackedPositionListItem(BaseModel):
    carriage_id: UUID
    procedure_ref: str
    title: Optional[str]
    confidence: str
    data_completeness: str
    parliament_summary: Dict[str, Any]
    council_summary: Dict[str, Any]
    user_stance: Optional[str] = None
    generated_at: Optional[datetime] = None


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

@router.get("/", response_model=List[TrackedPositionListItem], summary="List tracked files with position summary")
async def list_tracked_positions(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[TrackedPositionListItem]:
    tracks = (
        db.query(UserCarriageTrack)
        .filter(UserCarriageTrack.user_id == current_user.id)
        .limit(limit)
        .all()
    )
    out: List[TrackedPositionListItem] = []
    for t in tracks:
        carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == t.carriage_id).first()
        if not carriage:
            continue
        snap = db.query(FilePositionSnapshot).filter(FilePositionSnapshot.carriage_id == carriage.id).first()
        if not snap:
            # Try to generate it
            try:
                snap = await _ensure_snapshot(carriage, db)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[positions] failed to generate snapshot for %s: %s", carriage.oeil_procedure_ref, exc)
                continue
        if not snap:
            continue
        pp = snap.parliament_position or {}
        cp = snap.council_position or {}
        out.append(TrackedPositionListItem(
            carriage_id=carriage.id,
            procedure_ref=snap.procedure_ref,
            title=carriage.title,
            confidence=snap.confidence or "medium",
            data_completeness=snap.data_completeness or "partial",
            parliament_summary={
                "groups": len(pp.get("groups", [])),
                "amendments": (pp.get("amendment_activity") or {}).get("total", 0),
                "rapporteur": pp.get("rapporteur"),
                "rapporteur_group": pp.get("rapporteur_group"),
            },
            council_summary=(cp.get("summary") or {}),
            user_stance=(t.user_position or {}).get("stance") if t.user_position else None,
            generated_at=snap.generated_at,
        ))
    return out


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
