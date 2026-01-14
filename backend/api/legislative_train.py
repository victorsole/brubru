"""
Legislative Train API

FastAPI endpoints for Legislative Train Schedule data.
Provides access to trains, carriages, analytics, and user tracking.
"""

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
    CarriageStatusEnum
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
        logger.error(f"Failed to get trains: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trains")


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
        logger.error(f"Failed to get train statistics: {str(e)}")
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
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> CarriageListResponse:
    """Get carriages with filters"""
    try:
        query = db.query(LegislativeCarriage)

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
        logger.error(f"Failed to get carriages: {str(e)}")
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
        logger.error(f"Failed to get carriage details: {str(e)}")
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
        logger.error(f"Failed to get blocked files: {str(e)}")
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
        logger.error(f"Failed to get committee workload: {str(e)}")
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
        logger.error(f"Failed to predict timeline: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to predict timeline")


# ===== User Tracking Endpoints =====

@router.post(
    "/track/{carriage_id}",
    summary="Track legislative file",
    description="Subscribe to status updates for a legislative file"
)
async def track_carriage(
    carriage_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Track a legislative file for updates"""
    try:
        # Check if carriage exists
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.id == carriage_id
        ).first()

        if not carriage:
            raise HTTPException(status_code=404, detail="Carriage not found")

        # Check if already tracking
        existing = db.query(UserCarriageTrack).filter(
            UserCarriageTrack.user_id == current_user.id,
            UserCarriageTrack.carriage_id == carriage_id
        ).first()

        if existing:
            return {"message": "Already tracking this file"}

        # Create tracking record
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
        logger.error(f"Failed to track carriage: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to track file")


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
        logger.error(f"Failed to untrack carriage: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to untrack file")


@router.get(
    "/tracked",
    response_model=List[CarriageSchema],
    summary="Get tracked files",
    description="Get all legislative files tracked by current user"
)
async def get_tracked_carriages(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[CarriageSchema]:
    """Get user's tracked legislative files"""
    try:
        tracks = db.query(UserCarriageTrack).filter(
            UserCarriageTrack.user_id == current_user.id
        ).all()

        carriage_ids = [t.carriage_id for t in tracks]

        carriages = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.id.in_(carriage_ids)
        ).all()

        return [CarriageSchema.model_validate(c) for c in carriages]

    except Exception as e:
        logger.error(f"Failed to get tracked carriages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tracked files")
