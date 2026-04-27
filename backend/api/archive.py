"""
Archive API for My EU Bubble items with lifespan.

Items in My EU Bubble (tracked files, calendar events, consultations, committee work,
adopted texts, votes) accumulate over time. This router lets users archive items
proactively (Dismiss button) and supports the auto-archive scheduled job that hides
items past their natural lifespan (adopted laws, closed consultations, past events).

Endpoints:
    POST /api/archive/{entity_type}/{track_id}          -- archive a tracked item
    POST /api/archive/{entity_type}/{track_id}/restore  -- un-archive
    GET  /api/archive/list?entity_type=carriage         -- list archived items
    POST /api/archive/calendar/{event_id}               -- archive shared calendar event
    POST /api/archive/calendar/{event_id}/restore       -- un-archive calendar event

Allowed entity_type values: carriage, commission_doc, consultation, committee_work,
text_adopted, vote.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional, Literal
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime

from core.database import get_db
from api.auth import get_current_user
from models.user import User

router = APIRouter(prefix="/api/archive", tags=["Archive"])

# Map entity_type to its tracks table
ENTITY_TABLES = {
    "carriage": "user_carriage_tracks",
    "commission_doc": "user_commission_doc_tracks",
    "consultation": "user_consultation_tracks",
    "committee_work": "user_committee_work_tracks",
    "text_adopted": "user_text_adopted_tracks",
    "vote": "user_vote_tracks",
}

EntityType = Literal[
    "carriage", "commission_doc", "consultation", "committee_work", "text_adopted", "vote"
]


class ArchiveResponse(BaseModel):
    archived: bool
    entity_type: str
    track_id: int
    archived_at: Optional[datetime]
    archived_reason: Optional[str]


class ArchivedItem(BaseModel):
    track_id: int
    entity_type: str
    archived_at: datetime
    archived_reason: str


def _table_for(entity_type: str) -> str:
    if entity_type not in ENTITY_TABLES:
        raise HTTPException(status_code=400, detail=f"Unknown entity_type. Allowed: {list(ENTITY_TABLES.keys())}")
    return ENTITY_TABLES[entity_type]


@router.post("/{entity_type}/{track_id}", response_model=ArchiveResponse)
def archive_item(
    entity_type: EntityType,
    track_id: int,
    reason: str = Query("user", description="Archive reason: 'user', 'auto:adopted', 'auto:closed', 'auto:past'"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ArchiveResponse:
    """Mark a tracked item as archived. Idempotent."""
    tbl = _table_for(entity_type)
    row = db.execute(
        text(f"SELECT id, archived_at FROM {tbl} WHERE id = :id AND user_id = :uid"),
        {"id": track_id, "uid": str(user.id)},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Track not found or not owned by user")

    db.execute(
        text(f"UPDATE {tbl} SET archived_at = NOW(), archived_reason = :reason WHERE id = :id"),
        {"id": track_id, "reason": reason},
    )
    db.commit()

    refreshed = db.execute(
        text(f"SELECT archived_at, archived_reason FROM {tbl} WHERE id = :id"),
        {"id": track_id},
    ).fetchone()
    return ArchiveResponse(
        archived=True,
        entity_type=entity_type,
        track_id=track_id,
        archived_at=refreshed[0],
        archived_reason=refreshed[1],
    )


@router.post("/{entity_type}/{track_id}/restore", response_model=ArchiveResponse)
def restore_item(
    entity_type: EntityType,
    track_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ArchiveResponse:
    """Un-archive a previously archived tracked item."""
    tbl = _table_for(entity_type)
    row = db.execute(
        text(f"SELECT id FROM {tbl} WHERE id = :id AND user_id = :uid"),
        {"id": track_id, "uid": str(user.id)},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Track not found or not owned by user")

    db.execute(
        text(f"UPDATE {tbl} SET archived_at = NULL, archived_reason = NULL WHERE id = :id"),
        {"id": track_id},
    )
    db.commit()
    return ArchiveResponse(
        archived=False,
        entity_type=entity_type,
        track_id=track_id,
        archived_at=None,
        archived_reason=None,
    )


@router.get("/list", response_model=list[ArchivedItem])
def list_archived(
    entity_type: Optional[EntityType] = None,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ArchivedItem]:
    """List the user's archived items. If entity_type is omitted, returns across all types."""
    types = [entity_type] if entity_type else list(ENTITY_TABLES.keys())
    out: list[ArchivedItem] = []
    per_type_limit = max(1, limit // max(len(types), 1))
    for et in types:
        tbl = ENTITY_TABLES[et]
        rows = db.execute(
            text(
                f"SELECT id, archived_at, archived_reason FROM {tbl} "
                f"WHERE user_id = :uid AND archived_at IS NOT NULL "
                f"ORDER BY archived_at DESC LIMIT :lim"
            ),
            {"uid": str(user.id), "lim": per_type_limit},
        ).fetchall()
        for r in rows:
            out.append(ArchivedItem(track_id=r[0], entity_type=et, archived_at=r[1], archived_reason=r[2] or "user"))
    out.sort(key=lambda x: x.archived_at, reverse=True)
    return out[:limit]


# ----- Calendar events (shared rows; archive is a join table) -----

@router.post("/calendar/{event_id}")
def archive_calendar_event(
    event_id: UUID,
    reason: str = Query("user"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Archive a shared calendar event for the current user only."""
    db.execute(
        text(
            "INSERT INTO user_calendar_event_archives (user_id, event_id, archived_reason) "
            "VALUES (:uid, :eid, :reason) "
            "ON CONFLICT (user_id, event_id) DO UPDATE SET archived_at = NOW(), archived_reason = EXCLUDED.archived_reason"
        ),
        {"uid": str(user.id), "eid": str(event_id), "reason": reason},
    )
    db.commit()
    return {"archived": True, "event_id": str(event_id), "reason": reason}


@router.post("/calendar/{event_id}/restore")
def restore_calendar_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Restore (un-archive) a calendar event for the current user."""
    db.execute(
        text("DELETE FROM user_calendar_event_archives WHERE user_id = :uid AND event_id = :eid"),
        {"uid": str(user.id), "eid": str(event_id)},
    )
    db.commit()
    return {"archived": False, "event_id": str(event_id)}
