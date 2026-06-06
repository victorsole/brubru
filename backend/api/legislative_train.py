"""
Legislative Train API

FastAPI endpoints for Legislative Train Schedule data.
Provides access to trains, carriages, analytics, and user tracking.
"""

import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from core.database import get_db
from models.user import User
from models.legislative_train import (
    LegislativeTrain,
    LegislativeCarriage,
    UserCarriageTrack,
    CarriageStatusEnum,
    CarriageSourceEnum
)
from schemas.scrapers.legislative_train_schemas import (
    LegislativeTrain as TrainSchema,
    LegislativeCarriage as CarriageSchema,
    EnrichedCarriage,
    EnrichedCarriageResponse,
    TrainListResponse,
    CarriageListResponse,
    CarriageSearchFilters,
    TrainStatistics,
    CommitteeWorkload,
    BlockedFileAlert,
    TimelinePrediction
)
from services.scrapers.legislative_train_scraper import LegislativeTrainScraper
from services.scrapers.legislative_train_enricher import LegislativeTrainEnricher
from services.scrapers.legislative_train_analyzer import LegislativeTrainAnalyzer
from services.scrapers.oeil_scraper import OEILScraper
from services.tracking.tracked_files_seeder import sync_tracked_files_from_interests, _interest_list
from services.tracking.pi_committee_crosswalk import keywords_for_interests
from services.api_clients.eurlex_client import EURLexClient
from services.api_clients.european_parliament_client import EuropeanParliamentClient
from .auth import get_current_user

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/legislative-train", tags=["Legislative Train"])


# ===== Train Endpoints =====

@router.get(
    "/trains",
    response_model=TrainListResponse,
    summary="Get all legislative trains",
    description="Get all 7 EC priority trains with statistics"
)
async def get_all_trains(
    db: Session = Depends(get_db)
) -> TrainListResponse:
    """Get all 7 EC priority trains"""
    try:
        trains = db.query(LegislativeTrain).order_by(LegislativeTrain.priority_number).all()

        return TrainListResponse(
            trains=[TrainSchema.model_validate(t) for t in trains],
            total=len(trains),
            commission_term="2024-2029"
        )

    except Exception as e:
        logger.exception(f"Failed to get trains: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trains")


@router.get(
    "/my-interest-keywords",
    summary="Topic keywords for my policy interests",
    description=(
        "Lowercase topic keywords derived from the signed-in user's Policy "
        "Interests. The Legislative Train view uses them to flag files whose "
        "title matches the user's interests (train files carry no committee/policy "
        "metadata, so title-keyword matching is the available PI signal)."
    ),
)
async def get_my_interest_keywords(
    current_user: Optional[User] = Depends(get_current_user),
) -> dict:
    """Return the user's PI topic keywords for client-side title matching."""
    if not current_user:
        return {"keywords": []}
    interests = _interest_list(current_user)
    return {"keywords": sorted(keywords_for_interests(interests))}


@router.get(
    "/trains/{train_id}/statistics",
    response_model=TrainStatistics,
    summary="Get train statistics",
    description="Get comprehensive statistics for a specific train"
)
async def get_train_statistics(
    train_id: UUID,
    db: Session = Depends(get_db)
) -> TrainStatistics:
    """Get statistics for a train"""
    try:
        analyzer = LegislativeTrainAnalyzer(db)
        stats = analyzer.get_train_statistics(train_id)

        if not stats:
            raise HTTPException(status_code=404, detail="Train not found")

        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get train statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


# ===== Carriage Endpoints =====

@router.get(
    "/carriages",
    response_model=CarriageListResponse,
    summary="Get legislative carriages",
    description="Get legislative files with filtering options"
)
async def get_carriages(
    train_id: Optional[UUID] = Query(None, description="Filter by train"),
    status: Optional[CarriageStatusEnum] = Query(None, description="Filter by status"),
    committee: Optional[str] = Query(None, description="Filter by committee"),
    is_blocked: Optional[bool] = Query(None, description="Filter blocked files"),
    policy_areas: Optional[str] = Query(None, description="Filter by policy areas (comma-separated)"),
    search: Optional[str] = Query(None, description="Full-text search on title and procedure reference"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> CarriageListResponse:
    """Get carriages with filters"""
    try:
        query = db.query(LegislativeCarriage)

        # Full-text search on title (uses GIN index) + exact match on procedure ref
        if search and search.strip():
            search_term = search.strip()
            # Try procedure reference match first (exact substring)
            ref_filter = LegislativeCarriage.oeil_procedure_ref.ilike(f"%{search_term}%")
            # PostgreSQL full-text search on title using the existing GIN index
            # Convert search terms to tsquery: split words and join with &
            words = [w for w in search_term.split() if len(w) > 1]
            if words:
                ts_query = " & ".join(words)
                from sqlalchemy import func, text as sa_text
                title_filter = func.to_tsvector('english', LegislativeCarriage.title).match(ts_query)
                # Also try simple ILIKE as fallback for partial matches
                ilike_filter = LegislativeCarriage.title.ilike(f"%{search_term}%")
                query = query.filter(ref_filter | title_filter | ilike_filter)
            else:
                query = query.filter(ref_filter)

        # Apply filters
        if train_id:
            query = query.filter(LegislativeCarriage.train_id == train_id)

        if status:
            query = query.filter(LegislativeCarriage.current_status == status)

        if committee:
            query = query.filter(LegislativeCarriage.committees.contains([committee.upper()]))

        if is_blocked is not None:
            query = query.filter(LegislativeCarriage.is_blocked == is_blocked)

        if policy_areas:
            # Parse comma-separated policy areas
            areas = [area.strip() for area in policy_areas.split(',') if area.strip()]
            if areas:
                # Filter carriages that have at least one matching policy area
                query = query.filter(LegislativeCarriage.policy_areas.overlap(areas))

        # Get total count
        total = query.count()

        # Apply pagination
        carriages = query.offset(offset).limit(limit).all()

        # Build filters object
        filters = CarriageSearchFilters(
            train_id=train_id,
            status=status,
            committee=committee,
            is_blocked=is_blocked,
            limit=limit,
            offset=offset
        )

        return CarriageListResponse(
            carriages=[CarriageSchema.model_validate(c) for c in carriages],
            total=total,
            limit=limit,
            offset=offset,
            filters_applied=filters
        )

    except Exception as e:
        logger.exception(f"Failed to get carriages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve carriages")


@router.get(
    "/carriages/{carriage_id}",
    response_model=EnrichedCarriageResponse,
    summary="Get carriage details",
    description="Get full details for a legislative file with enrichment data"
)
async def get_carriage_details(
    carriage_id: UUID,
    include_related: bool = Query(True, description="Include related carriages"),
    include_prediction: bool = Query(True, description="Include timeline prediction"),
    db: Session = Depends(get_db)
) -> EnrichedCarriageResponse:
    """Get detailed carriage information"""
    try:
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.id == carriage_id
        ).first()

        if not carriage:
            raise HTTPException(status_code=404, detail="Carriage not found")

        # Convert to enriched schema
        enriched = EnrichedCarriage.model_validate(carriage)

        # Find related carriages
        related = []
        if include_related:
            # Find by same OEIL procedure or CELEX
            related_query = db.query(LegislativeCarriage).filter(
                LegislativeCarriage.id != carriage_id
            )

            if carriage.oeil_procedure_ref:
                related_query = related_query.filter(
                    LegislativeCarriage.oeil_procedure_ref == carriage.oeil_procedure_ref
                )
            elif carriage.celex_numbers:
                related_query = related_query.filter(
                    LegislativeCarriage.celex_numbers.overlap(carriage.celex_numbers)
                )

            related = related_query.limit(5).all()

        # Get timeline prediction
        prediction = None
        if include_prediction:
            analyzer = LegislativeTrainAnalyzer(db)
            prediction = analyzer.predict_timeline(carriage_id)

        return EnrichedCarriageResponse(
            carriage=enriched,
            related_carriages=[CarriageSchema.model_validate(r) for r in related],
            timeline_prediction=prediction
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get carriage details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve carriage")


# ===== Analytics Endpoints =====

@router.get(
    "/analytics/blocked-files",
    response_model=List[BlockedFileAlert],
    summary="Get blocked files",
    description="Find legislative files blocked for 9+ months"
)
async def get_blocked_files(
    min_days: int = Query(270, ge=1, description="Minimum days to consider blocked"),
    db: Session = Depends(get_db)
) -> List[BlockedFileAlert]:
    """Get blocked legislative files"""
    try:
        analyzer = LegislativeTrainAnalyzer(db)
        alerts = analyzer.get_blocked_files(min_days)

        return alerts

    except Exception as e:
        logger.exception(f"Failed to get blocked files: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve blocked files")


@router.get(
    "/analytics/committee/{committee_code}",
    response_model=CommitteeWorkload,
    summary="Get committee workload",
    description="Analyze workload for a specific committee"
)
async def get_committee_workload(
    committee_code: str,
    db: Session = Depends(get_db)
) -> CommitteeWorkload:
    """Get committee workload analysis"""
    try:
        analyzer = LegislativeTrainAnalyzer(db)
        workload = analyzer.get_committee_workload(committee_code.upper())

        if not workload:
            raise HTTPException(status_code=404, detail="Committee not found or has no files")

        return workload

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get committee workload: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve workload")


@router.get(
    "/analytics/prediction/{carriage_id}",
    response_model=TimelinePrediction,
    summary="Predict timeline",
    description="Predict completion timeline for a legislative file"
)
async def predict_carriage_timeline(
    carriage_id: UUID,
    db: Session = Depends(get_db)
) -> TimelinePrediction:
    """Predict timeline for a carriage"""
    try:
        analyzer = LegislativeTrainAnalyzer(db)
        prediction = analyzer.predict_timeline(carriage_id)

        if not prediction:
            raise HTTPException(status_code=404, detail="Carriage not found")

        return prediction

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to predict timeline: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to predict timeline")


# ===== User Tracking Endpoints =====

# NOTE: literal-path routes MUST be declared before /track/{carriage_id} so FastAPI
# doesn't match "by-procedure" as the UUID path parameter. Same for DELETE.
@router.post(
    "/track/by-procedure",
    summary="Track legislative file by procedure reference",
    description="Subscribe to status updates using OEIL procedure reference (e.g., 2021/0106(COD))"
)
async def track_carriage_by_procedure(
    procedure_ref: str = Query(..., description="OEIL procedure reference"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Track a legislative file by OEIL procedure reference"""
    try:
        # Find carriage by procedure reference
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.oeil_procedure_ref == procedure_ref
        ).first()

        if not carriage:
            raise HTTPException(
                status_code=404,
                detail=f"No legislative file found for procedure: {procedure_ref}"
            )

        # Check if already tracking
        existing = db.query(UserCarriageTrack).filter(
            UserCarriageTrack.user_id == current_user.id,
            UserCarriageTrack.carriage_id == carriage.id
        ).first()

        if existing:
            return {
                "message": "Already tracking this file",
                "carriage_id": str(carriage.id),
                "procedure_ref": procedure_ref
            }

        # Create tracking record
        track = UserCarriageTrack(
            user_id=current_user.id,
            carriage_id=carriage.id
        )

        db.add(track)
        db.commit()

        return {
            "message": "Now tracking legislative file",
            "carriage_id": str(carriage.id),
            "procedure_ref": procedure_ref,
            "title": carriage.title
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to track carriage by procedure: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to track file")


@router.post(
    "/track/{carriage_id}",
    summary="Track legislative file by ID",
    description="Subscribe to status updates for a legislative file by carriage UUID"
)
async def track_carriage(
    carriage_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Track a legislative file for updates"""
    try:
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.id == carriage_id
        ).first()
        if not carriage:
            raise HTTPException(status_code=404, detail="Carriage not found")

        existing = db.query(UserCarriageTrack).filter(
            UserCarriageTrack.user_id == current_user.id,
            UserCarriageTrack.carriage_id == carriage_id
        ).first()
        if existing:
            return {"message": "Already tracking this file"}

        track = UserCarriageTrack(
            user_id=current_user.id,
            carriage_id=carriage_id
        )
        db.add(track)
        db.commit()
        return {"message": "Now tracking legislative file", "carriage_id": str(carriage_id)}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to track carriage: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to track file")


@router.post(
    "/track-by-celex",
    summary="Track legislative file by CELEX number",
    description="Find a legislative carriage whose celex_numbers array contains this CELEX, then track it."
)
async def track_carriage_by_celex(
    celex: str = Query(..., description="CELEX number (e.g. 52026PC0321)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.celex_numbers.any(celex)
        ).first()

        if not carriage:
            raise HTTPException(status_code=404, detail=f"No legislative file found for CELEX: {celex}")

        existing = db.query(UserCarriageTrack).filter(
            UserCarriageTrack.user_id == current_user.id,
            UserCarriageTrack.carriage_id == carriage.id,
        ).first()

        if existing:
            return {"message": "Already tracking this file", "carriage_id": str(carriage.id), "celex": celex}

        track = UserCarriageTrack(user_id=current_user.id, carriage_id=carriage.id)
        db.add(track)
        db.commit()
        return {"message": "Now tracking legislative file", "carriage_id": str(carriage.id), "celex": celex}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to track by CELEX {celex}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to track: {e}")


@router.delete(
    "/track/by-procedure",
    summary="Untrack legislative file by procedure reference",
    description="Unsubscribe from status updates using OEIL procedure reference"
)
async def untrack_carriage_by_procedure(
    procedure_ref: str = Query(..., description="OEIL procedure reference"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stop tracking a legislative file by OEIL procedure reference"""
    try:
        # Find carriage by procedure reference
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.oeil_procedure_ref == procedure_ref
        ).first()

        if not carriage:
            raise HTTPException(
                status_code=404,
                detail=f"No legislative file found for procedure: {procedure_ref}"
            )

        # Find tracking record
        track = db.query(UserCarriageTrack).filter(
            UserCarriageTrack.user_id == current_user.id,
            UserCarriageTrack.carriage_id == carriage.id
        ).first()

        if not track:
            raise HTTPException(status_code=404, detail="Not tracking this file")

        db.delete(track)
        db.commit()

        return {
            "message": "Stopped tracking legislative file",
            "procedure_ref": procedure_ref
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to untrack carriage by procedure: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to untrack file")


@router.delete(
    "/track/{carriage_id}",
    summary="Untrack legislative file",
    description="Unsubscribe from status updates"
)
async def untrack_carriage(
    carriage_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stop tracking a legislative file"""
    try:
        track = db.query(UserCarriageTrack).filter(
            UserCarriageTrack.user_id == current_user.id,
            UserCarriageTrack.carriage_id == carriage_id
        ).first()
        if not track:
            raise HTTPException(status_code=404, detail="Not tracking this file")
        db.delete(track)
        db.commit()
        return {"message": "Stopped tracking legislative file"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to untrack carriage: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to untrack file")


@router.post(
    "/sync-from-interests",
    summary="Populate tracked files from your Policy Interests",
    description=(
        "Auto-populates My Tracked Files from the user's MEUB Policy Interests: "
        "maps each interest to its EP committee(s), then pre-tracks the ongoing "
        "OEIL legislative and non-legislative files led by those committees. "
        "Idempotent, never duplicates an existing track."
    ),
)
async def sync_from_interests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Seed pre-checked tracked files from the user's policy interests."""
    return sync_tracked_files_from_interests(db, current_user)


@router.get(
    "/tracked",
    summary="Get tracked files",
    description="Get all legislative files tracked by current user"
)
async def get_tracked_carriages(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's tracked legislative files with tracking metadata"""
    try:
        from datetime import datetime, timezone

        # Get tracks with carriage data
        tracks = db.query(UserCarriageTrack).filter(
            UserCarriageTrack.user_id == current_user.id
        ).all()

        tracked_files = []
        for track in tracks:
            carriage = db.query(LegislativeCarriage).filter(
                LegislativeCarriage.id == track.carriage_id
            ).first()

            if carriage:
                # Use days_in_current_status from model, or calculate from last_updated
                days_in_status = carriage.days_in_current_status
                if days_in_status is None and carriage.last_updated:
                    delta = datetime.now(timezone.utc) - carriage.last_updated.replace(tzinfo=timezone.utc)
                    days_in_status = delta.days

                tracked_files.append({
                    "id": str(track.id),
                    "carriage_id": str(carriage.id),
                    "file_id": carriage.file_id,  # String slug for detail endpoint
                    "title": carriage.title,
                    "current_status": carriage.current_status.value if carriage.current_status else "unknown",
                    "oeil_procedure_ref": carriage.oeil_procedure_ref,
                    "celex_numbers": carriage.celex_numbers,  # For loading in Amendator
                    "lead_committee": carriage.committees[0] if carriage.committees else None,
                    "tracked_since": track.tracked_since.isoformat() if track.tracked_since else None,
                    "last_updated": carriage.last_updated.isoformat() if carriage.last_updated else None,
                    "is_blocked": carriage.is_blocked,
                    "days_in_current_status": days_in_status
                })

        return {"tracked_files": tracked_files}

    except Exception as e:
        logger.exception(f"Failed to get tracked carriages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tracked files")


@router.get(
    "/hot-this-week",
    summary="Hot files this week",
    description="Top legislative files with recent activity (last 14 days). Used by My EU Bubble dashboard widget."
)
async def get_hot_this_week_carriages(
    db: Session = Depends(get_db),
    limit: int = 10
):
    """Return up to N carriages with recent activity, ranked by recency.

    Public endpoint (no auth required) so the suggestion widget renders for
    anonymous visitors. Filters:
      - recent activity: is_recently_updated TRUE, or last_updated within 14d,
        or days_in_current_status < 14
      - title quality: ignore items whose title is just a CELEX/document
        identifier (e.g. "CELEX:32016L2370R(01)") or empty. Users can't tell
        what those are without clicking.
      - over-fetch then re-rank, so quality filtering doesn't starve the list.
    """
    try:
        from datetime import datetime, timedelta, timezone
        import re
        from sqlalchemy import or_

        cutoff = datetime.now(timezone.utc) - timedelta(days=14)

        # Over-fetch — we filter out low-quality titles client-side
        carriages = (
            db.query(LegislativeCarriage)
              .filter(
                  or_(
                      LegislativeCarriage.is_recently_updated.is_(True),
                      LegislativeCarriage.last_updated >= cutoff,
                      LegislativeCarriage.days_in_current_status < 14,
                  )
              )
              .order_by(LegislativeCarriage.last_updated.desc().nullslast())
              .limit(500)  # cover the whole recent window; a batch of placeholder-titled
              .all()       # OEIL backfills sit at the top of last_updated and would
        )                  # otherwise crowd out the real-titled hot files.

        # CELEX-only titles look like: CELEX:32016L2370R(01), 32016L2370,
        # CELEX:32026D02446 — uninformative, skip.
        CELEX_PATTERN = re.compile(r"^(CELEX[:\s]*)?[0-9]{5}[A-Z][0-9]{4}([A-Z]\([0-9]+\))?$", re.IGNORECASE)
        # Placeholder titles from OEIL backfills: "Procedure File: 2025/2880(RSP)".
        # The real descriptive title was never scraped — these read as gibberish,
        # so they must not surface in the widget.
        PROC_FILE_PATTERN = re.compile(r"^Procedure File:\s*\d{4}/\d+\([A-Z]+\)", re.IGNORECASE)

        def is_meaningful(title: str | None) -> bool:
            if not title:
                return False
            t = title.strip()
            if len(t) < 25:
                return False
            if CELEX_PATTERN.match(t):
                return False
            if PROC_FILE_PATTERN.match(t):
                return False
            return True

        items = []
        for c in carriages:
            if not is_meaningful(c.title):
                continue
            items.append({
                "id": str(c.id),
                "carriage_id": str(c.id),
                "file_id": c.file_id,
                "title": c.title.strip(),
                "current_status": c.current_status.value if c.current_status else "unknown",
                "oeil_procedure_ref": c.oeil_procedure_ref,
                "celex_numbers": c.celex_numbers or [],
                "lead_committee": c.lead_committee or (c.committees or [None])[0],
                "last_updated": c.last_updated.isoformat() if c.last_updated else None,
                "days_in_current_status": c.days_in_current_status,
                "is_recently_updated": bool(c.is_recently_updated),
            })
            if len(items) >= limit:
                break

        return {"items": items, "total": len(items)}
    except Exception as e:
        logger.exception(f"Failed to get hot-this-week carriages: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve hot files")


# ===== EUR-Lex Integration Endpoints =====

@router.get(
    "/carriages/{carriage_id}/eurlex",
    summary="Get EUR-Lex documents for carriage",
    description="Fetch EUR-Lex document metadata and relationships for a legislative file's CELEX numbers"
)
async def get_carriage_eurlex_data(
    carriage_id: UUID,
    include_relationships: bool = Query(True, description="Include document relationships"),
    db: Session = Depends(get_db)
):
    """
    Get EUR-Lex document data for a carriage.

    Uses the CELLAR SPARQL API to fetch:
    - Document metadata (title, date, type, author)
    - Document relationships (amendments, repeals, implementations)
    """
    try:
        # Get carriage
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.id == carriage_id
        ).first()

        if not carriage:
            raise HTTPException(status_code=404, detail="Carriage not found")

        if not carriage.celex_numbers:
            return {
                "carriage_id": str(carriage_id),
                "eurlex_documents": [],
                "message": "No CELEX numbers found for this carriage"
            }

        # Initialize EUR-Lex client
        eurlex_client = EURLexClient()

        eurlex_docs = []

        try:
            for celex in carriage.celex_numbers[:5]:  # Limit to 5 CELEX numbers
                doc_data = {
                    "celex": celex,
                    "url": f"https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:{celex}"
                }

                # Fetch metadata via SPARQL
                metadata = await eurlex_client.get_document_by_celex(celex)
                if metadata:
                    doc_data["title"] = metadata.get("title")
                    doc_data["date"] = metadata.get("date")
                    doc_data["type"] = metadata.get("type")
                    doc_data["subject"] = metadata.get("subject")
                    doc_data["author"] = metadata.get("author")
                    doc_data["uri"] = metadata.get("uri")

                # Fetch relationships
                if include_relationships:
                    relationships = await eurlex_client.get_document_relationships(celex)
                    if relationships:
                        doc_data["relationships"] = {
                            "amended_by": relationships.get("amended_by", []),
                            "amends": relationships.get("amends", []),
                            "repealed_by": relationships.get("repealed_by", []),
                            "repeals": relationships.get("repeals", []),
                            "implemented_by": relationships.get("implemented_by", [])
                        }

                eurlex_docs.append(doc_data)

        finally:
            await eurlex_client.close()

        return {
            "carriage_id": str(carriage_id),
            "carriage_title": carriage.title,
            "eurlex_documents": eurlex_docs,
            "total_documents": len(eurlex_docs)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get EUR-Lex data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve EUR-Lex data")


@router.get(
    "/eurlex/{celex}",
    summary="Get EUR-Lex document by CELEX",
    description="Fetch EUR-Lex document metadata and relationships directly by CELEX number"
)
async def get_eurlex_document(
    celex: str,
    include_relationships: bool = Query(True, description="Include document relationships"),
    language: str = Query("en", description="Language code for title")
):
    """
    Get EUR-Lex document by CELEX number.

    CELEX format: [sector][year][type][number] (e.g., "32024R1689" for AI Act)
    """
    try:
        eurlex_client = EURLexClient()

        try:
            # Fetch metadata
            metadata = await eurlex_client.get_document_by_celex(celex, language)

            if not metadata:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document not found for CELEX: {celex}"
                )

            doc_data = {
                "celex": celex,
                "url": f"https://eur-lex.europa.eu/legal-content/{language.upper()}/ALL/?uri=CELEX:{celex}",
                "title": metadata.get("title"),
                "date": metadata.get("date"),
                "type": metadata.get("type"),
                "subject": metadata.get("subject"),
                "author": metadata.get("author"),
                "uri": metadata.get("uri"),
                "language": language
            }

            # Fetch relationships
            if include_relationships:
                relationships = await eurlex_client.get_document_relationships(celex)
                if relationships:
                    doc_data["relationships"] = relationships

        finally:
            await eurlex_client.close()

        return doc_data

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get EUR-Lex document: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve EUR-Lex document")


@router.get(
    "/eurlex/{celex}/related",
    summary="Get related EUR-Lex documents",
    description="Find documents that amend, repeal, or implement the specified document"
)
async def get_eurlex_related_documents(
    celex: str
):
    """
    Get documents related to a CELEX number.

    Returns all documents that:
    - Amend this document
    - Are amended by this document
    - Repeal this document
    - Are repealed by this document
    - Implement this document
    """
    try:
        eurlex_client = EURLexClient()

        try:
            relationships = await eurlex_client.get_document_relationships(celex)

            if not relationships or all(not v for v in relationships.values()):
                return {
                    "celex": celex,
                    "relationships": {},
                    "total_related": 0,
                    "message": "No related documents found"
                }

            total_related = sum(len(v) for v in relationships.values() if isinstance(v, list))

        finally:
            await eurlex_client.close()

        return {
            "celex": celex,
            "relationships": relationships,
            "total_related": total_related
        }

    except Exception as e:
        logger.exception(f"Failed to get related documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve related documents")


# ===== OEIL Integration Endpoints =====

@router.get(
    "/carriages/{carriage_id}/oeil",
    summary="Get OEIL procedure data for carriage",
    description="Fetch full OEIL procedure data including key players, events, forecasts, and documents"
)
async def get_carriage_oeil_data(
    carriage_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get OEIL procedure data for a carriage.

    Returns the full OEIL procedure including:
    - Basic info (title, status, subjects)
    - Key players (rapporteur, shadow rapporteurs, committees, Commission DG)
    - Key events (legislative timeline)
    - Forecasts (upcoming events)
    - Documentation (EP, Commission, Council documents)
    - Additional info (EUR-Lex links, related procedures)
    """
    try:
        # Get carriage
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.id == carriage_id
        ).first()

        if not carriage:
            raise HTTPException(status_code=404, detail="Carriage not found")

        if not carriage.oeil_procedure_ref:
            return {
                "carriage_id": str(carriage_id),
                "oeil_procedure": None,
                "message": "No OEIL procedure reference found for this carriage"
            }

        # Initialize OEIL scraper
        oeil_scraper = OEILScraper()

        try:
            # Fetch procedure data
            procedure = await oeil_scraper.get_procedure(carriage.oeil_procedure_ref)

            if not procedure:
                return {
                    "carriage_id": str(carriage_id),
                    "oeil_procedure_ref": carriage.oeil_procedure_ref,
                    "oeil_procedure": None,
                    "message": f"Could not fetch OEIL procedure {carriage.oeil_procedure_ref}"
                }

            return {
                "carriage_id": str(carriage_id),
                "carriage_title": carriage.title,
                "oeil_procedure_ref": carriage.oeil_procedure_ref,
                "oeil_procedure": procedure
            }

        finally:
            await oeil_scraper.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get OEIL data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve OEIL data")


@router.get(
    "/carriages/{carriage_id}/key-players",
    summary="Get key players for carriage",
    description="Get rapporteur, shadow rapporteurs, committees, and Commission DG for a legislative file"
)
async def get_carriage_key_players(
    carriage_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get key players for a carriage from OEIL.

    Returns a flat array of key players:
    - Rapporteur with photo and political group
    - Shadow rapporteurs
    - Commissioner (if available)
    """
    try:
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.id == carriage_id
        ).first()

        if not carriage:
            raise HTTPException(status_code=404, detail="Carriage not found")

        if not carriage.oeil_procedure_ref:
            return {
                "carriage_id": str(carriage_id),
                "key_players": [],
                "message": "No OEIL procedure reference found"
            }

        oeil_scraper = OEILScraper()

        try:
            procedure = await oeil_scraper.get_procedure(carriage.oeil_procedure_ref)

            if not procedure or not isinstance(procedure, dict):
                return {
                    "carriage_id": str(carriage_id),
                    "oeil_procedure_ref": carriage.oeil_procedure_ref,
                    "key_players": [],
                    "message": "Could not fetch OEIL procedure"
                }

            # Extract key players section from OEIL
            oeil_key_players = procedure.get("key_players", {})

            # Transform nested OEIL structure into flat array
            key_players_list = []

            # Extract rapporteur from committee_responsible
            committee_responsible = oeil_key_players.get("committee_responsible")
            if isinstance(committee_responsible, dict):
                rapporteur = committee_responsible.get("rapporteur")
                committee_code = committee_responsible.get("code", "")

                if isinstance(rapporteur, dict) and rapporteur.get("name"):
                    key_players_list.append({
                        "name": rapporteur.get("name"),
                        "role": f"Rapporteur ({committee_code})" if committee_code else "Rapporteur",
                        "political_group": rapporteur.get("political_group"),
                        "country": rapporteur.get("country"),
                        "mep_id": rapporteur.get("mep_id"),
                        "photo_url": rapporteur.get("photo_url"),
                    })

                # Extract shadow rapporteurs
                shadows = committee_responsible.get("shadow_rapporteurs", [])
                for shadow in shadows:
                    if isinstance(shadow, dict) and shadow.get("name"):
                        key_players_list.append({
                            "name": shadow.get("name"),
                            "role": f"Shadow Rapporteur ({committee_code})" if committee_code else "Shadow Rapporteur",
                            "political_group": shadow.get("political_group"),
                            "country": shadow.get("country"),
                            "mep_id": shadow.get("mep_id"),
                            "photo_url": shadow.get("photo_url"),
                        })

            # Extract rapporteurs from opinion committees
            for committee in oeil_key_players.get("committees_opinion", []):
                if isinstance(committee, dict):
                    rapporteur = committee.get("rapporteur")
                    committee_code = committee.get("code", "")

                    if isinstance(rapporteur, dict) and rapporteur.get("name"):
                        key_players_list.append({
                            "name": rapporteur.get("name"),
                            "role": f"Opinion Rapporteur ({committee_code})" if committee_code else "Opinion Rapporteur",
                            "political_group": rapporteur.get("political_group"),
                            "country": rapporteur.get("country"),
                            "mep_id": rapporteur.get("mep_id"),
                            "photo_url": rapporteur.get("photo_url"),
                        })

            # Add Commission DG if available and has meaningful content
            commission_dg = oeil_key_players.get("commission_dg")
            if commission_dg and isinstance(commission_dg, str) and len(commission_dg.strip()) > 2:
                dg_str = commission_dg.strip()
                key_players_list.append({
                    "name": dg_str,
                    "role": "European Commission",
                    "political_group": None,
                    "country": None,
                    "mep_id": None,
                    "photo_url": None,
                })

            # Add Commissioner if available and has meaningful content
            commissioner = oeil_key_players.get("commissioner")
            if commissioner and isinstance(commissioner, str) and len(commissioner.strip()) > 2:
                commissioner_str = commissioner.strip()

                # Detect if this is a portfolio name vs actual Commissioner name
                is_portfolio = (
                    commissioner_str.lower().endswith('commissioner') or
                    len(commissioner_str.split()) == 1 or
                    commissioner_str.lower() in ['justice', 'internal market', 'digital', 'trade',
                                                  'environment', 'health', 'transport', 'energy']
                )

                if is_portfolio:
                    # Portfolio only - format as "Commissioner for X"
                    portfolio = commissioner_str.replace(' Commissioner', '').replace('Commissioner', '').strip()
                    if portfolio and len(portfolio) > 2:
                        display_name = f"Commissioner for {portfolio}"
                        key_players_list.append({
                            "name": display_name,
                            "role": "European Commission",
                            "political_group": None,
                            "country": None,
                            "mep_id": None,
                            "photo_url": None,
                        })
                    # Skip if portfolio is empty or too short
                else:
                    # Actual name
                    key_players_list.append({
                        "name": commissioner_str,
                        "role": "Commissioner",
                        "political_group": None,
                        "country": None,
                        "mep_id": None,
                        "photo_url": None,
                    })

            # Dedupe by MEP identity, not (name, role). OEIL returns the same
            # person multiple times because:
            #  (a) `name` sometimes carries a "(Group)" suffix and sometimes doesn't
            #      ("METZ Tilly (Greens/EFA)" vs "METZ Tilly"),
            #  (b) the same MEP appears under "rapporteur" AND "shadow_rapporteurs"
            #      in OEIL when the source page conflates roles.
            # Identity key: mep_id when present, else normalised name. Keep the most
            # senior role per person (Rapporteur > Shadow > Opinion > other).
            import re as _re
            ROLE_PRIORITY = {"rapporteur": 0, "shadow rapporteur": 1, "opinion rapporteur": 2}

            def _role_rank(role: str) -> int:
                r = (role or "").lower()
                for k, v in ROLE_PRIORITY.items():
                    if r.startswith(k):
                        return v
                return 99

            from services.mep_groups_cache import enrich_political_group
            NAME_GROUP_RE = _re.compile(r"\s*\(([^)]+)\)\s*$")

            def _normalise(p: dict) -> dict:
                # Strip trailing "(Group)" from name; if political_group is missing,
                # lift the parenthetical into political_group.
                p = dict(p)
                name = (p.get("name") or "").strip()
                m = NAME_GROUP_RE.search(name)
                if m:
                    parenthetical = m.group(1).strip()
                    p["name"] = NAME_GROUP_RE.sub("", name).strip()
                    if not p.get("political_group"):
                        p["political_group"] = parenthetical
                return p

            by_identity: dict[str, dict] = {}
            for raw in key_players_list:
                p = _normalise(raw)
                # Authoritative enrichment from EP profile cache (no fabrication).
                enrich_political_group(p)
                key = str(p.get("mep_id") or p.get("name", "").lower() or p.get("role", "").lower())
                existing = by_identity.get(key)
                if existing is None or _role_rank(p.get("role", "")) < _role_rank(existing.get("role", "")):
                    by_identity[key] = p

            deduped = list(by_identity.values())

            return {
                "carriage_id": str(carriage_id),
                "carriage_title": carriage.title,
                "oeil_procedure_ref": carriage.oeil_procedure_ref,
                "key_players": deduped,
            }

        finally:
            await oeil_scraper.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get key players: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve key players")


# OEIL "Key events" / "Documentation gateway" table boilerplate that the scraper
# sometimes dumps into an event description, especially for RSP (resolution)
# procedures whose OEIL page layout differs from COD files.
_OEIL_BOILERPLATE_RE = re.compile(
    r"(key events"
    r"|date\s+event\s+reference\s+summary"
    r"|document type\s+committee\s+reference\s+date\s+summary"
    r"|\bpdf\b|\bsika\b)",
    re.IGNORECASE,
)


def _clean_oeil_text(raw) -> str:
    """Collapse whitespace and strip OEIL scrape boilerplate from a text field."""
    if not raw or not isinstance(raw, str):
        return ""
    text = re.sub(r"\s+", " ", raw).strip()
    text = _OEIL_BOILERPLATE_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _sanitize_timeline_events(events) -> list:
    """Drop scrape-boilerplate-only events and clean the remaining text fields."""
    cleaned = []
    for e in events or []:
        if not isinstance(e, dict):
            continue
        desc = _clean_oeil_text(e.get("description"))
        summ = _clean_oeil_text(e.get("summary"))
        etype = (e.get("event_type") or "").strip()
        has_real_type = bool(etype) and etype.lower() != "event"
        # Keep only events that carry real information after cleaning.
        if not (desc or summ or e.get("result") or has_real_type):
            continue
        cleaned.append({**e, "description": desc, "summary": summ})
    return cleaned


@router.get(
    "/carriages/{carriage_id}/timeline",
    summary="Get legislative timeline for carriage",
    description="Get key events and milestones from OEIL for a legislative file"
)
async def get_carriage_timeline(
    carriage_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get legislative timeline (key events) for a carriage.

    Returns chronological list of events:
    - Commission proposal
    - Committee votes
    - Plenary readings
    - Council positions
    - Final act adoption
    """
    try:
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.id == carriage_id
        ).first()

        if not carriage:
            raise HTTPException(status_code=404, detail="Carriage not found")

        if not carriage.oeil_procedure_ref:
            return {
                "carriage_id": str(carriage_id),
                "timeline": [],
                "message": "No OEIL procedure reference found"
            }

        oeil_scraper = OEILScraper()

        try:
            procedure = await oeil_scraper.get_procedure(carriage.oeil_procedure_ref)

            if not procedure or not isinstance(procedure, dict):
                return {
                    "carriage_id": str(carriage_id),
                    "oeil_procedure_ref": carriage.oeil_procedure_ref,
                    "timeline": [],
                    "message": "Could not fetch OEIL procedure"
                }

            # Extract key events
            key_events = procedure.get("key_events", {})
            events = key_events.get("events", []) if isinstance(key_events, dict) else []
            events = _sanitize_timeline_events(events)

            return {
                "carriage_id": str(carriage_id),
                "carriage_title": carriage.title,
                "oeil_procedure_ref": carriage.oeil_procedure_ref,
                "timeline": events,
                "total_events": len(events)
            }

        finally:
            await oeil_scraper.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get timeline: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve timeline")


@router.get(
    "/carriages/{carriage_id}/forecasts",
    summary="Get forecasts for carriage",
    description="Get upcoming/foreseen events from OEIL for a legislative file"
)
async def get_carriage_forecasts(
    carriage_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get forecasts (upcoming events) for a carriage.

    Returns foreseen events:
    - Committee votes
    - Plenary sessions
    - Council meetings
    """
    try:
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.id == carriage_id
        ).first()

        if not carriage:
            raise HTTPException(status_code=404, detail="Carriage not found")

        if not carriage.oeil_procedure_ref:
            return {
                "carriage_id": str(carriage_id),
                "forecasts": [],
                "message": "No OEIL procedure reference found"
            }

        oeil_scraper = OEILScraper()

        try:
            procedure = await oeil_scraper.get_procedure(carriage.oeil_procedure_ref)

            if not procedure or not isinstance(procedure, dict):
                return {
                    "carriage_id": str(carriage_id),
                    "oeil_procedure_ref": carriage.oeil_procedure_ref,
                    "forecasts": [],
                    "message": "Could not fetch OEIL procedure"
                }

            # Extract forecasts
            forecasts_section = procedure.get("forecasts", {})
            forecasts = forecasts_section.get("forecasts", []) if isinstance(forecasts_section, dict) else []

            return {
                "carriage_id": str(carriage_id),
                "carriage_title": carriage.title,
                "oeil_procedure_ref": carriage.oeil_procedure_ref,
                "forecasts": forecasts,
                "total_forecasts": len(forecasts)
            }

        finally:
            await oeil_scraper.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get forecasts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve forecasts")


@router.get(
    "/oeil/{procedure_ref}",
    summary="Get OEIL procedure by reference",
    description="Fetch full OEIL procedure data directly by procedure reference"
)
async def get_oeil_procedure(
    procedure_ref: str
):
    """
    Get OEIL procedure by reference.

    Procedure reference format: YYYY/NNNN(XXX)
    Example: 2024/0176(COD)
    """
    try:
        oeil_scraper = OEILScraper()

        try:
            procedure = await oeil_scraper.get_procedure(procedure_ref)

            if not procedure:
                raise HTTPException(
                    status_code=404,
                    detail=f"Procedure not found: {procedure_ref}"
                )

            return {
                "procedure_ref": procedure_ref,
                "procedure": procedure
            }

        finally:
            await oeil_scraper.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get OEIL procedure: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve OEIL procedure")


# ===== Active Procedures Search (EP Open Data + OEIL) =====

@router.get(
    "/procedures/search",
    summary="Search active EU legislative procedures",
    description="Search for ongoing legislative procedures from EP Open Data API and OEIL"
)
async def search_active_procedures(
    query: Optional[str] = Query(None, description="Search text in procedure title/reference"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    Search active EU legislative procedures.

    This searches the EP Open Data API for procedures, providing access to
    ongoing legislation beyond the Legislative Train (Commission priorities).

    Returns procedures with:
    - Procedure reference (e.g., 2024/0176(COD))
    - Title and status
    - Type (ordinary legislative, consultation, etc.)
    """
    try:
        ep_client = EuropeanParliamentClient()

        try:
            # Get procedures from EP Open Data API
            procedures = await ep_client.get_procedures(limit=limit, offset=offset)

            # Filter by query if provided
            if query:
                query_lower = query.lower()
                procedures = [
                    p for p in procedures
                    if query_lower in p.get("label", "").lower()
                    or query_lower in p.get("reference", "").lower()
                ]

            return {
                "procedures": procedures,
                "total": len(procedures),
                "limit": limit,
                "offset": offset,
                "source": "ep_opendata"
            }

        finally:
            await ep_client.close()

    except Exception as e:
        logger.exception(f"Failed to search procedures: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search procedures")


@router.post(
    "/track/oeil",
    summary="Track an OEIL procedure directly",
    description="Create a carriage entry from an OEIL procedure reference and track it"
)
async def track_oeil_procedure(
    procedure_ref: str = Query(..., description="OEIL procedure reference (e.g., 2024/0176(COD))"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Track an OEIL procedure that's not in the Legislative Train.

    This endpoint:
    1. Fetches full procedure data from OEIL
    2. Creates a new LegislativeCarriage entry (source=oeil_direct)
    3. Creates a UserCarriageTrack for the current user

    Use this to track ongoing legislation that isn't in the Commission's
    Legislative Train priorities.
    """
    try:
        # Check if carriage already exists for this procedure ref
        existing = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.oeil_procedure_ref == procedure_ref
        ).first()

        if existing:
            # Carriage exists, just track it
            existing_track = db.query(UserCarriageTrack).filter(
                UserCarriageTrack.user_id == current_user.id,
                UserCarriageTrack.carriage_id == existing.id
            ).first()

            if existing_track:
                return {
                    "message": "Already tracking this procedure",
                    "carriage_id": str(existing.id),
                    "procedure_ref": procedure_ref
                }

            # Create tracking entry
            track = UserCarriageTrack(
                user_id=current_user.id,
                carriage_id=existing.id
            )
            db.add(track)
            db.commit()

            return {
                "message": "Now tracking procedure",
                "carriage_id": str(existing.id),
                "procedure_ref": procedure_ref,
                "title": existing.title
            }

        # Fetch full OEIL procedure data
        oeil_scraper = OEILScraper()

        try:
            procedure = await oeil_scraper.get_procedure(procedure_ref)

            if not procedure or isinstance(procedure, dict) and procedure.get("error"):
                raise HTTPException(
                    status_code=404,
                    detail=f"Procedure not found in OEIL: {procedure_ref}"
                )

            # Extract basic info from OEIL data
            basic_info = procedure.get("basic_info", {})
            key_players = procedure.get("key_players", {})

            title = basic_info.get("title") or f"Procedure {procedure_ref}"
            status = basic_info.get("status", "")

            # Map OEIL status to our status enum
            status_mapping = {
                "awaiting": CarriageStatusEnum.TABLED,
                "committee": CarriageStatusEnum.TABLED,
                "plenary": CarriageStatusEnum.CLOSE_TO_ADOPTION,
                "completed": CarriageStatusEnum.COMPLETED,
                "adopted": CarriageStatusEnum.ADOPTED,
                "rejected": CarriageStatusEnum.WITHDRAWN,
                "withdrawn": CarriageStatusEnum.WITHDRAWN,
            }

            carriage_status = CarriageStatusEnum.ANNOUNCED  # default
            status_lower = status.lower()
            for key, enum_val in status_mapping.items():
                if key in status_lower:
                    carriage_status = enum_val
                    break

            # Extract committee info
            committee_responsible = key_players.get("committee_responsible", {})
            lead_committee = committee_responsible.get("code") if isinstance(committee_responsible, dict) else None

            # Create new carriage
            file_id = f"oeil-{procedure_ref.replace('/', '-').replace('(', '-').replace(')', '')}"

            carriage = LegislativeCarriage(
                file_id=file_id,
                title=title,
                description=basic_info.get("title"),  # OEIL often has extended title in description
                current_status=carriage_status,
                source=CarriageSourceEnum.OEIL_DIRECT,
                oeil_procedure_ref=procedure_ref,
                oeil_procedure_data=procedure,
                lead_committee=lead_committee,
            )

            db.add(carriage)
            db.flush()  # Get the ID

            # Create tracking entry
            track = UserCarriageTrack(
                user_id=current_user.id,
                carriage_id=carriage.id
            )
            db.add(track)
            db.commit()

            return {
                "message": "Created and tracking new OEIL procedure",
                "carriage_id": str(carriage.id),
                "procedure_ref": procedure_ref,
                "title": title,
                "status": carriage_status.value,
                "source": "oeil_direct"
            }

        finally:
            await oeil_scraper.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to track OEIL procedure: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to track procedure: {str(e)}")


# ===== Amendment Cross-Reference Endpoints (Priority #4) =====

@router.get(
    "/carriages/{carriage_id}/amendments",
    summary="Get amendments for carriage",
    description="Get all user amendments linked to a specific legislative file"
)
async def get_carriage_amendments(
    carriage_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get amendments linked to a specific carriage"""
    from services.amendator.amendment_linker import get_amendment_linker

    try:
        linker = get_amendment_linker(db)
        amendments = linker.get_amendments_for_carriage(carriage_id, current_user.id)

        return {
            "carriage_id": str(carriage_id),
            "amendments": [a.to_dict() for a in amendments],
            "count": len(amendments)
        }

    except Exception as e:
        logger.exception(f"Failed to get amendments for carriage: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve amendments")


@router.get(
    "/carriages/{carriage_id}/emeeting-documents",
    summary="EP committee documents for a tracked file",
    description=(
        "The substantive EP committee-meeting documents tied to this file's OEIL "
        "procedure: the draft report, the amendments and compromise amendments, the "
        "opinions and draft opinions from associated committees, reasoned opinions, "
        "and any agreed text / letter of agreement / draft resolution / working "
        "document. Grouped by document type, newest first, each with a direct PDF "
        "URL. (Voting lists live in Votes; minutes in Transcripts; the agenda in My "
        "EU Calendar — see the eMeeting routing.)"
    ),
)
async def get_carriage_emeeting_documents(
    carriage_id: UUID,
    db: Session = Depends(get_db),
):
    from services.linking.emeeting_links import grouped_dossier_docs
    carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == carriage_id).first()
    if not carriage:
        raise HTTPException(status_code=404, detail="Carriage not found")
    procs = [carriage.oeil_procedure_ref] if carriage.oeil_procedure_ref else []
    result = grouped_dossier_docs(db, procs)
    return {"procedure_ref": carriage.oeil_procedure_ref, **result}


def _journey_payload(row: Optional[dict], current_hash: Optional[str]) -> dict:
    """Shape a stored journey row for the API, flagging staleness."""
    if not row:
        return {"status": "absent"}
    import json as _json
    layers = row["layers"] if isinstance(row["layers"], list) else _json.loads(row["layers"] or "[]")
    comparison = row["comparison"] if isinstance(row["comparison"], dict) else _json.loads(row["comparison"] or "{}")
    return {
        "status": row["status"],
        "procedure_ref": row["procedure_ref"],
        "is_legislative": row["is_legislative"],
        "summary": row["summary"],
        "layers": layers,
        "comparison": comparison,
        "engine": row["engine"],
        "model": row["model"],
        "source_doc_count": row["source_doc_count"],
        "generated_at": row["generated_at"],
        "stale": bool(current_hash and current_hash != row["doc_set_hash"]),
    }


@router.get(
    "/carriages/{carriage_id}/journey",
    summary="AI comparative analysis of a dossier's text journey",
    description=(
        "**What it does**\nReturns the cached AI comparison of how this dossier's "
        "text changes through the committee stage: the Commission proposal, the "
        "rapporteur's draft report, MEPs' amendments, the compromise amendments, "
        "and the final voting list (a resolution skips the proposal layer).\n\n"
        "**When to use it**\nThe 'Legislative journey' summary in the file-detail "
        "modal and the detailed panel in Position Analysis.\n\n"
        "**Input**\nThe carriage id.\n\n"
        "**You get back**\n`status` (ready / absent / generating / error), a short "
        "`summary`, the per-layer analysis, and the cross-layer comparison. "
        "`stale=true` means new committee documents have arrived since it was built."
    ),
)
async def get_carriage_journey(
    carriage_id: UUID,
    db: Session = Depends(get_db),
):
    from services.analysis.legislative_journey_service import get_journey, current_doc_set_hash
    carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == carriage_id).first()
    if not carriage:
        raise HTTPException(status_code=404, detail="Carriage not found")
    ref = carriage.oeil_procedure_ref
    if not ref:
        return {"status": "absent"}
    return _journey_payload(get_journey(db, ref), current_doc_set_hash(db, ref))


@router.post(
    "/carriages/{carriage_id}/journey",
    summary="Generate (or refresh) the dossier journey analysis",
    description=(
        "Builds the AI comparative analysis on demand for this dossier and caches "
        "it. Used when the analysis is absent or stale. Takes ~20-60s. The "
        "precompute job fills most tracked files ahead of time, so this is the "
        "gap-filler when a user opens a file that has not been analysed yet."
    ),
)
async def generate_carriage_journey(
    carriage_id: UUID,
    force: bool = Query(False, description="Regenerate even if a fresh analysis exists"),
    db: Session = Depends(get_db),
):
    from services.analysis.legislative_journey_service import (
        get_journey, generate_journey, current_doc_set_hash,
    )
    carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == carriage_id).first()
    if not carriage:
        raise HTTPException(status_code=404, detail="Carriage not found")
    ref = carriage.oeil_procedure_ref
    if not ref:
        raise HTTPException(status_code=400, detail="Carriage has no procedure reference")

    cur_hash = current_doc_set_hash(db, ref)
    existing = get_journey(db, ref)
    if existing and not force and existing["status"] == "ready" and existing["doc_set_hash"] == cur_hash:
        return _journey_payload(existing, cur_hash)

    result = await generate_journey(db, carriage)
    if result is None:
        return {"status": "error", "detail": "No analysable committee documents for this dossier."}
    return _journey_payload(result, current_doc_set_hash(db, ref))


@router.get(
    "/tracked/amendment-counts",
    summary="Get amendment counts for tracked files",
    description="Get the number of amendments for each tracked legislative file"
)
async def get_tracked_amendment_counts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get amendment counts for all tracked files"""
    from services.amendator.amendment_linker import get_amendment_linker

    try:
        linker = get_amendment_linker(db)
        counts = linker.count_amendments_by_carriage(current_user.id)

        return {
            "amendment_counts": counts
        }

    except Exception as e:
        logger.exception(f"Failed to get amendment counts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve amendment counts")


# ===== CELEX Enrichment Endpoint =====

@router.post(
    "/carriages/{carriage_id}/enrich-celex",
    summary="Fetch and populate CELEX numbers from OEIL",
    description="Fetches CELEX numbers from OEIL procedure data and updates the carriage"
)
async def enrich_carriage_celex(
    carriage_id: UUID,
    force: bool = Query(False, description="Force re-enrichment even if CELEX exists"),
    db: Session = Depends(get_db)
):
    """
    Fetch CELEX numbers from OEIL and update the carriage.

    This endpoint:
    1. Gets the carriage's OEIL procedure reference
    2. Scrapes OEIL for EUR-Lex document links
    3. Extracts CELEX numbers from those links
    4. Updates the carriage in the database
    5. Returns the CELEX numbers
    """
    import re

    try:
        # Get carriage
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.id == carriage_id
        ).first()

        if not carriage:
            raise HTTPException(status_code=404, detail="Carriage not found")

        # If already has CELEX and not forcing re-enrichment, return cached
        if carriage.celex_numbers and len(carriage.celex_numbers) > 0 and not force:
            return {
                "carriage_id": str(carriage_id),
                "celex_numbers": carriage.celex_numbers,
                "source": "cached",
                "message": "CELEX numbers already present"
            }

        if not carriage.oeil_procedure_ref:
            raise HTTPException(
                status_code=400,
                detail="No OEIL procedure reference available to fetch CELEX"
            )

        # Initialize OEIL scraper
        oeil_scraper = OEILScraper()
        celex_numbers = []

        try:
            # Fetch full procedure data from OEIL
            procedure = await oeil_scraper.get_procedure(carriage.oeil_procedure_ref)

            if procedure:
                # Extract CELEX from additional_info
                additional = procedure.get("additional_info", {})
                if additional:
                    # Check eurlex_links
                    eurlex_links = additional.get("eurlex_links", [])
                    for link in eurlex_links:
                        url = link.get("url", "") if isinstance(link, dict) else str(link)
                        # Extract CELEX from URL patterns (case-insensitive)
                        # Pattern 1: uri=celex:52025PC0986 or CELEX:52025PC0986
                        celex_match = re.search(r'[Cc][Ee][Ll][Ee][Xx][=:](\d+[A-Z]+\d+)', url)
                        if celex_match:
                            celex_numbers.append(celex_match.group(1))
                        else:
                            # Pattern 2: /52025PC0986/ in path
                            celex_match = re.search(r'/(\d{5}[A-Z]{1,4}\d{3,4})/', url)
                            if celex_match:
                                celex_numbers.append(celex_match.group(1))
                            else:
                                # Pattern 3: ?celex=52025PC0986
                                celex_match = re.search(r'[?&]celex=(\d+[A-Z]+\d+)', url, re.IGNORECASE)
                                if celex_match:
                                    celex_numbers.append(celex_match.group(1))

                    # Check direct celex_number field
                    if additional.get("celex_number"):
                        celex_numbers.append(additional.get("celex_number"))

                # Also check documentation section
                documentation = procedure.get("documentation", {})
                if documentation:
                    for doc_type in ["commission", "ep_committee", "council"]:
                        docs = documentation.get(doc_type, [])
                        for doc in docs:
                            if isinstance(doc, dict):
                                url = doc.get("url", "")
                                # Case-insensitive CELEX extraction
                                celex_match = re.search(r'[Cc][Ee][Ll][Ee][Xx][=:](\d+[A-Z]+\d+)', url)
                                if celex_match:
                                    celex_numbers.append(celex_match.group(1))
                                else:
                                    celex_match = re.search(r'/(\d{5}[A-Z]{1,4}\d{3,4})/', url)
                                    if celex_match:
                                        celex_numbers.append(celex_match.group(1))

            # Deduplicate
            celex_numbers = list(set(celex_numbers))

            # If no CELEX found in OEIL data, scrape OEIL page for COM document number
            if not celex_numbers and carriage.oeil_procedure_ref:
                try:
                    import aiohttp
                    logger.info(f"OEIL had no CELEX, scraping OEIL page for COM number: {carriage.oeil_procedure_ref}")

                    # Fetch OEIL page directly to find COM document number
                    oeil_url = f"https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference={carriage.oeil_procedure_ref}"

                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            oeil_url,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                html = await resp.text()
                                # Look for COM(year)number pattern
                                com_matches = re.findall(r'COM\((\d{4})\)(\d+)', html)
                                if com_matches:
                                    # Get the first COM document (usually the main proposal)
                                    year, number = com_matches[0]
                                    potential_celex = f"5{year}PC{number.zfill(4)}"

                                    # Verify this CELEX exists via SPARQL
                                    sparql_query = f"""
                                    PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
                                    SELECT ?celex WHERE {{
                                        ?doc cdm:resource_legal_id_celex ?celex .
                                        FILTER(STR(?celex) = "{potential_celex}")
                                    }}
                                    LIMIT 1
                                    """

                                    async with session.get(
                                        "https://publications.europa.eu/webapi/rdf/sparql",
                                        params={"query": sparql_query, "format": "application/json"},
                                        timeout=aiohttp.ClientTimeout(total=30)
                                    ) as sparql_resp:
                                        if sparql_resp.status == 200:
                                            sparql_result = await sparql_resp.json()
                                            bindings = sparql_result.get("results", {}).get("bindings", [])
                                            if bindings:
                                                celex_numbers.append(potential_celex)
                                                logger.info(f"Found CELEX from COM number: {potential_celex}")
                except Exception as scrape_err:
                    logger.warning(f"OEIL page scrape fallback failed: {scrape_err}")

            if celex_numbers:
                # Update carriage in database
                carriage.celex_numbers = celex_numbers
                db.commit()

                logger.info(f"Enriched carriage {carriage_id} with CELEX: {celex_numbers}")

                return {
                    "carriage_id": str(carriage_id),
                    "celex_numbers": celex_numbers,
                    "source": "oeil+eurlex_sparql",
                    "message": f"Found {len(celex_numbers)} CELEX number(s)"
                }
            else:
                return {
                    "carriage_id": str(carriage_id),
                    "celex_numbers": [],
                    "source": "oeil+eurlex_sparql",
                    "message": "No CELEX numbers found in OEIL or EUR-Lex"
                }

        finally:
            await oeil_scraper.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to enrich carriage CELEX: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch CELEX: {str(e)}")


# ===== OEIL Sync Endpoints =====

@router.post(
    "/sync/oeil",
    summary="Sync OEIL XML feeds",
    description="Fetch latest procedures from OEIL XML feeds and add to database"
)
async def sync_oeil_feeds(
    days: int = Query(default=7, ge=1, le=30, description="Days to look back"),
    force: bool = Query(default=False, description="Update existing entries"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync OEIL XML feeds to database.

    Fetches from:
    - latest-procedures: New legislative procedures (COD, INI, RSP, etc.)
    - latest-information-documents: COM/SWD documents
    - latest-committees-reports-tabled: Committee reports

    Requires Blue tier subscription.
    """
    # Check user tier
    if current_user.subscription_tier not in ['blue', 'admin']:
        raise HTTPException(
            status_code=403,
            detail="OEIL sync requires Blue tier subscription"
        )

    try:
        from services.scrapers.oeil_sync_service import OEILSyncService

        logger.info(f"[SYNC] User {current_user.email} triggered OEIL sync (days={days}, force={force})")

        service = OEILSyncService(db=db)
        result = await service.sync_all(
            procedures_days=days,
            documents_days=days,
            reports_days=30,
            skip_existing=not force
        )

        logger.info(
            f"[SYNC] Complete: added={result['added']}, "
            f"updated={result['updated']}, skipped={result['skipped']}"
        )

        return {
            "status": "success",
            "added": result['added'],
            "updated": result['updated'],
            "skipped": result['skipped'],
            "errors": result['errors'],
            "items": result['items'][:50]  # Limit response size
        }

    except Exception as e:
        logger.exception(f"[SYNC] Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post(
    "/sync/oeil/lookup",
    summary="Look up a single OEIL procedure",
    description="Add a specific procedure to the database by scraping its OEIL page"
)
async def lookup_oeil_procedure(
    reference: str = Query(..., description="OEIL procedure reference (e.g. 2025/0726(COD))"),
    force: bool = Query(default=False, description="Update even if already exists"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Look up and add a single OEIL procedure by reference.

    Bypasses the 30-day XML feed limit by scraping the OEIL procedure page directly.
    Useful for adding older procedures not captured by the regular sync.

    Requires Blue tier subscription.
    """
    if current_user.subscription_tier not in ['blue', 'admin']:
        raise HTTPException(
            status_code=403,
            detail="OEIL lookup requires Blue tier subscription"
        )

    try:
        from services.scrapers.oeil_sync_service import OEILSyncService

        logger.info(f"[SYNC] User {current_user.email} looking up OEIL procedure: {reference}")

        service = OEILSyncService(db=db)
        result = await service.sync_single_procedure(reference, force=force)

        return result

    except Exception as e:
        logger.exception(f"[SYNC] Lookup failed for {reference}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lookup failed: {str(e)}")


# ===== EUR-Lex Sync Endpoints =====

@router.post(
    "/sync/eurlex",
    summary="Sync EUR-Lex RSS feeds",
    description="Fetch latest legislation and proposals from EUR-Lex RSS feeds and add to database"
)
async def sync_eurlex_feeds(
    days: int = Query(default=7, ge=1, le=30, description="Days to look back"),
    force: bool = Query(default=False, description="Update existing entries"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync EUR-Lex RSS feeds to database.

    Fetches from:
    - parliament_council_legislation: EP and Council adopted acts
    - commission_proposals: COM documents and proposals

    Requires Blue tier subscription.
    """
    # Check user tier
    if current_user.subscription_tier not in ['blue', 'admin']:
        raise HTTPException(
            status_code=403,
            detail="EUR-Lex sync requires Blue tier subscription"
        )

    try:
        from services.scrapers.eurlex_sync_service import EURLexSyncService

        logger.info(f"[SYNC] User {current_user.email} triggered EUR-Lex sync (days={days}, force={force})")

        service = EURLexSyncService(db=db)
        result = await service.sync_all(
            legislation_days=days,
            proposals_days=days,
            skip_existing=not force
        )

        logger.info(
            f"[SYNC] Complete: added={result['added']}, "
            f"updated={result['updated']}, skipped={result['skipped']}"
        )

        return {
            "status": "success",
            "added": result['added'],
            "updated": result['updated'],
            "skipped": result['skipped'],
            "errors": result['errors'],
            "items": result['items'][:50]  # Limit response size
        }

    except Exception as e:
        logger.exception(f"[SYNC] Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
