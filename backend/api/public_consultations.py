"""
Public Consultations API

FastAPI endpoints for EC Public Consultations (Have Your Say portal).

Routes:
- GET /api/consultations - List consultations with filters
- GET /api/consultations/{id} - Get consultation details
- POST /api/consultations/{id}/track - Track a consultation
- DELETE /api/consultations/{id}/track - Untrack a consultation
- GET /api/consultations/tracked - Get user's tracked consultations
- POST /api/consultations/{id}/proposals - Generate AI proposals (Blue tier)
- GET /api/consultations/{id}/alignment - Get alignment assessment (Blue tier)
- POST /api/consultations/sync - Trigger sync (admin only)
- GET /api/consultations/dgs - List Directorate-Generals
- GET /api/consultations/policy-areas - List policy areas

Access Control:
- Yellow+: Full read access, tracking
- Blue: AI proposals, alignment analysis
- Admin: Sync trigger

Created: January 2026
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from uuid import UUID
from datetime import datetime, date

from core.database import get_db
from models.user import User
from models.public_consultation import (
    PublicConsultation,
    ConsultationDocument,
    UserConsultationTrack,
    UserConsultationInput,
    ConsultationTypeEnum,
    ConsultationStatusEnum,
    SubmissionStatusEnum,
)
from schemas.public_consultation_schemas import (
    ConsultationListItem,
    ConsultationDetailResponse,
    ConsultationListResponse,
    ConsultationDocumentResponse,
    TrackedConsultationResponse,
    TrackedConsultationsListResponse,
    TrackConsultationRequest,
    UpdateTrackingRequest,
    ConsultationType,
    ConsultationStatus,
    SubmissionStatus,
    SyncStatusResponse,
    SyncResultResponse,
    DGInfo,
    DGListResponse,
    PolicyAreaInfo,
    PolicyAreasListResponse,
)
from knowledge_base.ec_consultations import (
    DGS,
    POLICY_AREA_LABELS,
    PolicyArea,
    get_dg_full_name,
)
from .auth import get_current_user

import logging

logger = logging.getLogger(__name__)


# ============================================================================
# AI Analysis Response Models (inline for now)
# ============================================================================

from pydantic import BaseModel as PydanticBaseModel

class AnalysisResponse(PydanticBaseModel):
    """AI analysis response model."""
    consultation_id: UUID
    executive_summary: str
    key_questions: List[str]
    stakeholder_categories: List[str]
    submission_requirements: Optional[str] = None
    legislation_context: Optional[str] = None
    key_provisions_under_review: List[str] = []
    potential_impacts: List[str] = []
    recommended_focus_areas: List[str] = []
    confidence_score: float
    generated_at: datetime


class ProposalItemResponse(PydanticBaseModel):
    """Single proposal in response."""
    id: int
    question_addressed: str
    proposed_response: str
    supporting_arguments: List[str]
    evidence_citations: List[str] = []
    source_documents: List[str]
    tone_suggestion: str
    confidence_score: float


class ProposalsResponse(PydanticBaseModel):
    """Full proposals response."""
    consultation_id: UUID
    overall_strategy: str
    recommended_tone: str
    key_messages: List[str]
    proposals: List[ProposalItemResponse]
    tokens_used: int
    generated_at: datetime


class GenerateProposalsRequest(PydanticBaseModel):
    """Request to generate proposals."""
    document_ids: List[UUID] = []
    focus_areas: List[str] = []


class RefineProposalRequest(PydanticBaseModel):
    """Request to refine a proposal."""
    proposal_id: int
    user_feedback: str

router = APIRouter(prefix="/api/consultations", tags=["Public Consultations"])


# ============================================================================
# Helper Functions
# ============================================================================

def check_yellow_tier(user: User):
    """Check user has Yellow tier or above."""
    if user.subscription_tier not in ['yellow', 'blue', 'admin']:
        raise HTTPException(
            status_code=403,
            detail="Yellow subscription required to access public consultations"
        )


def check_blue_tier(user: User):
    """Check user has Blue tier or above."""
    if user.subscription_tier not in ['blue', 'admin']:
        raise HTTPException(
            status_code=403,
            detail="Blue subscription required for AI features"
        )


def consultation_to_list_item(
    consultation: PublicConsultation,
    is_tracked: bool = False
) -> ConsultationListItem:
    """Convert database model to list item response."""
    days_remaining = None
    is_closing_soon = False

    if consultation.end_date:
        delta = consultation.end_date - date.today()
        days_remaining = max(0, delta.days)
        is_closing_soon = 0 < days_remaining <= 7

    return ConsultationListItem(
        id=consultation.id,
        initiative_id=consultation.initiative_id,
        title=consultation.title,
        short_title=consultation.short_title,
        consultation_type=ConsultationType(consultation.consultation_type.value),
        status=ConsultationStatus(consultation.status.value),
        dg_responsible=consultation.dg_responsible,
        dg_name=get_dg_full_name(consultation.dg_responsible) if consultation.dg_responsible else None,
        policy_areas=consultation.policy_areas or [],
        start_date=consultation.start_date,
        end_date=consultation.end_date,
        days_remaining=days_remaining,
        is_closing_soon=is_closing_soon,
        feedback_count=consultation.feedback_count,
        relevance_score=consultation.relevance_score,
        is_tracked=is_tracked,
        portal_url=consultation.portal_url,
    )


# ============================================================================
# List Consultations
# ============================================================================

@router.get(
    "",
    response_model=ConsultationListResponse,
    summary="Get public consultations",
    description="Get consultations with filtering, sorting, and pagination"
)
async def get_consultations(
    status: Optional[ConsultationStatus] = Query(None, description="Filter by status"),
    consultation_type: Optional[ConsultationType] = Query(None, description="Filter by type"),
    dg: Optional[str] = Query(None, description="Filter by DG code"),
    policy_area: Optional[str] = Query(None, description="Filter by policy area"),
    search: Optional[str] = Query(None, description="Search in title/description"),
    closing_soon: Optional[bool] = Query(None, description="Filter closing within 7 days"),
    min_relevance: Optional[int] = Query(None, ge=0, le=100, description="Minimum relevance"),
    sort_by: str = Query("end_date", description="Sort: end_date, relevance_score, feedback_count, last_updated"),
    sort_desc: bool = Query(False, description="Sort descending"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ConsultationListResponse:
    """Get public consultations with filters."""
    check_yellow_tier(current_user)

    try:
        query = db.query(PublicConsultation)

        filters_applied = {}

        # Apply filters
        if status:
            query = query.filter(PublicConsultation.status == status.value)
            filters_applied['status'] = status.value

            # When filtering for "open", exclude consultations whose deadline has passed
            if status.value == 'open':
                today = date.today()
                query = query.filter(
                    or_(
                        PublicConsultation.end_date >= today,
                        PublicConsultation.end_date.is_(None)
                    )
                )

        if consultation_type:
            query = query.filter(PublicConsultation.consultation_type == consultation_type.value)
            filters_applied['consultation_type'] = consultation_type.value

        if dg:
            query = query.filter(PublicConsultation.dg_responsible == dg.upper())
            filters_applied['dg'] = dg.upper()

        if policy_area:
            query = query.filter(PublicConsultation.policy_areas.contains([policy_area]))
            filters_applied['policy_area'] = policy_area

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    PublicConsultation.title.ilike(search_term),
                    PublicConsultation.description.ilike(search_term),
                    PublicConsultation.initiative_id.ilike(search_term)
                )
            )
            filters_applied['search'] = search

        if closing_soon:
            today = date.today()
            week_later = date.today().replace(day=today.day + 7)
            query = query.filter(
                and_(
                    PublicConsultation.end_date >= today,
                    PublicConsultation.end_date <= week_later,
                    PublicConsultation.status == ConsultationStatusEnum.OPEN
                )
            )
            filters_applied['closing_soon'] = True

        if min_relevance is not None:
            query = query.filter(PublicConsultation.relevance_score >= min_relevance)
            filters_applied['min_relevance'] = min_relevance

        # Get total count
        total = query.count()

        # Apply sorting
        sort_column = getattr(PublicConsultation, sort_by, PublicConsultation.end_date)
        if sort_desc:
            query = query.order_by(sort_column.desc().nulls_last())
        else:
            query = query.order_by(sort_column.asc().nulls_last())

        # Apply pagination
        consultations = query.offset(offset).limit(limit).all()

        # Get tracked IDs for current user
        tracked_ids = {
            str(t.consultation_id)
            for t in db.query(UserConsultationTrack.consultation_id).filter(
                UserConsultationTrack.user_id == current_user.id
            ).all()
        }

        # Build response items
        items = [
            consultation_to_list_item(c, str(c.id) in tracked_ids)
            for c in consultations
        ]

        return ConsultationListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            filters_applied=filters_applied if filters_applied else None
        )

    except Exception as e:
        logger.error(f"Failed to get consultations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve consultations")


# ============================================================================
# Reference Data (MUST be before /{consultation_id} route)
# ============================================================================

@router.get(
    "/dgs",
    response_model=DGListResponse,
    summary="List Directorate-Generals"
)
async def get_dgs() -> DGListResponse:
    """Get list of EC Directorate-Generals."""
    dgs = [
        DGInfo(code=dg.code, name=dg.name, full_name=dg.full_name)
        for dg in DGS
    ]
    return DGListResponse(dgs=dgs, total=len(dgs))


@router.get(
    "/policy-areas",
    response_model=PolicyAreasListResponse,
    summary="List policy areas"
)
async def get_policy_areas() -> PolicyAreasListResponse:
    """Get list of policy areas."""
    areas = [
        PolicyAreaInfo(code=pa.value, name=POLICY_AREA_LABELS.get(pa, pa.value))
        for pa in PolicyArea
    ]
    return PolicyAreasListResponse(policy_areas=areas, total=len(areas))


# ============================================================================
# Tracked Consultations (MUST be before /{consultation_id} route)
# ============================================================================

@router.get(
    "/tracked",
    response_model=TrackedConsultationsListResponse,
    summary="Get tracked consultations"
)
async def get_tracked_consultations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> TrackedConsultationsListResponse:
    """Get user's tracked consultations."""
    check_yellow_tier(current_user)

    try:
        tracks = db.query(UserConsultationTrack).filter(
            UserConsultationTrack.user_id == current_user.id
        ).all()

        items = []
        for track in tracks:
            consultation = db.query(PublicConsultation).filter(
                PublicConsultation.id == track.consultation_id
            ).first()

            if consultation:
                items.append(TrackedConsultationResponse(
                    consultation=consultation_to_list_item(consultation, is_tracked=True),
                    tracked_since=track.tracked_since,
                    notify_on_deadline=track.notify_on_deadline,
                    notify_on_outcome=track.notify_on_outcome,
                    notify_days_before=track.notify_days_before,
                    submission_status=SubmissionStatus(track.submission_status.value),
                    notes=track.notes,
                    priority=track.priority,
                    last_notified_at=track.last_notified_at,
                ))

        return TrackedConsultationsListResponse(
            items=items,
            total=len(items)
        )

    except Exception as e:
        logger.error(f"Failed to get tracked consultations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tracked consultations")


# ============================================================================
# Sync (MUST be before /{consultation_id} route)
# ============================================================================

@router.get(
    "/sync/status",
    response_model=SyncStatusResponse,
    summary="Get sync status"
)
async def get_sync_status(
    db: Session = Depends(get_db)
) -> SyncStatusResponse:
    """Get sync status and statistics."""
    try:
        total = db.query(PublicConsultation).count()

        # Count by status
        open_count = db.query(PublicConsultation).filter(
            PublicConsultation.status == ConsultationStatusEnum.OPEN
        ).count()
        closed_count = db.query(PublicConsultation).filter(
            PublicConsultation.status == ConsultationStatusEnum.CLOSED
        ).count()
        outcome_count = db.query(PublicConsultation).filter(
            PublicConsultation.status == ConsultationStatusEnum.OUTCOME_PUBLISHED
        ).count()

        # Last sync time
        last_item = db.query(PublicConsultation).order_by(
            PublicConsultation.scraped_at.desc()
        ).first()
        last_sync = last_item.scraped_at if last_item else None

        # Count by DG
        dg_counts = db.query(
            PublicConsultation.dg_responsible,
            func.count(PublicConsultation.id)
        ).filter(
            PublicConsultation.dg_responsible.isnot(None)
        ).group_by(PublicConsultation.dg_responsible).all()
        by_dg = {dg: count for dg, count in dg_counts if dg}

        return SyncStatusResponse(
            last_sync=last_sync,
            total_consultations=total,
            open_count=open_count,
            closed_count=closed_count,
            outcome_count=outcome_count,
            consultations_by_dg=by_dg,
        )

    except Exception as e:
        logger.error(f"Failed to get sync status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sync status")


@router.post(
    "/sync",
    response_model=SyncResultResponse,
    summary="Trigger sync (Admin)"
)
async def trigger_sync(
    status_filter: Optional[str] = Query(None, description="Status: open, closed, outcome"),
    max_pages: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SyncResultResponse:
    """Trigger consultation sync (admin only)."""
    try:
        if current_user.subscription_tier not in ['blue', 'admin']:
            raise HTTPException(
                status_code=403,
                detail="Blue subscription required to trigger sync"
            )

        from services.scrapers.consultation_sync_service import ConsultationSyncService
        import time

        start_time = time.time()

        service = ConsultationSyncService(db=db)

        if status_filter == 'open':
            result = await service.sync_open(max_pages=max_pages)
        elif status_filter == 'closed':
            result = await service.sync_closed(max_pages=max_pages)
        elif status_filter == 'outcome':
            result = await service.sync_outcomes(max_pages=max_pages)
        else:
            result = await service.sync_all(max_pages_per_status=max_pages)

        duration = time.time() - start_time

        return SyncResultResponse(
            added=result['added'],
            updated=result['updated'],
            skipped=result['skipped'],
            errors=result['errors'],
            status_changes=result.get('status_changes', 0),
            duration_seconds=duration
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run sync: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


# ============================================================================
# Get Single Consultation
# ============================================================================

@router.get(
    "/{consultation_id}",
    response_model=ConsultationDetailResponse,
    summary="Get consultation details"
)
async def get_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ConsultationDetailResponse:
    """Get full details of a consultation."""
    check_yellow_tier(current_user)

    try:
        consultation = db.query(PublicConsultation).filter(
            PublicConsultation.id == consultation_id
        ).first()

        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")

        # Calculate days remaining
        days_remaining = None
        is_closing_soon = False
        if consultation.end_date:
            delta = consultation.end_date - date.today()
            days_remaining = max(0, delta.days)
            is_closing_soon = 0 < days_remaining <= 7

        # Get documents
        documents = [
            ConsultationDocumentResponse.model_validate(doc)
            for doc in consultation.documents
        ]

        # Check if tracked
        track = db.query(UserConsultationTrack).filter(
            UserConsultationTrack.user_id == current_user.id,
            UserConsultationTrack.consultation_id == consultation_id
        ).first()

        is_tracked = track is not None
        user_notes = track.notes if track else None
        tracked_since = track.tracked_since if track else None
        submission_status = SubmissionStatus(track.submission_status.value) if track else None

        return ConsultationDetailResponse(
            id=consultation.id,
            initiative_id=consultation.initiative_id,
            publication_id=consultation.publication_id,
            title=consultation.title,
            short_title=consultation.short_title,
            description=consultation.description,
            full_description=consultation.full_description,
            objectives=consultation.objectives,
            target_group=consultation.target_group,
            consultation_type=ConsultationType(consultation.consultation_type.value),
            status=ConsultationStatus(consultation.status.value),
            dg_responsible=consultation.dg_responsible,
            dg_name=get_dg_full_name(consultation.dg_responsible) if consultation.dg_responsible else None,
            policy_areas=consultation.policy_areas or [],
            start_date=consultation.start_date,
            end_date=consultation.end_date,
            days_remaining=days_remaining,
            is_closing_soon=is_closing_soon,
            feedback_count=consultation.feedback_count,
            views_count=consultation.views_count,
            portal_url=consultation.portal_url,
            feedback_url=consultation.feedback_url,
            com_references=consultation.com_references or [],
            celex_numbers=consultation.celex_numbers or [],
            outcome_summary=consultation.outcome_summary,
            outcome_published_date=consultation.outcome_published_date,
            outcome_document_url=consultation.outcome_document_url,
            relevance_score=consultation.relevance_score,
            documents=documents,
            is_tracked=is_tracked,
            user_notes=user_notes,
            tracked_since=tracked_since,
            submission_status=submission_status,
            created_at=consultation.created_at,
            last_updated=consultation.last_updated,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get consultation {consultation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve consultation")


# ============================================================================
# Tracking Actions (on specific consultations)
# ============================================================================

@router.post(
    "/{consultation_id}/track",
    status_code=status.HTTP_201_CREATED,
    summary="Track a consultation"
)
async def track_consultation(
    consultation_id: UUID,
    request: TrackConsultationRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start tracking a consultation."""
    check_yellow_tier(current_user)

    try:
        # Check consultation exists
        consultation = db.query(PublicConsultation).filter(
            PublicConsultation.id == consultation_id
        ).first()

        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")

        # Check if already tracking
        existing = db.query(UserConsultationTrack).filter(
            UserConsultationTrack.user_id == current_user.id,
            UserConsultationTrack.consultation_id == consultation_id
        ).first()

        if existing:
            return {"message": "Already tracking this consultation", "id": str(consultation_id)}

        # Create tracking record
        if request is None:
            request = TrackConsultationRequest()

        track = UserConsultationTrack(
            user_id=current_user.id,
            consultation_id=consultation_id,
            notify_on_deadline=request.notify_on_deadline,
            notify_on_outcome=request.notify_on_outcome,
            notify_days_before=request.notify_days_before,
            notes=request.notes,
            priority=request.priority,
            tracked_since=datetime.now()
        )
        db.add(track)
        db.commit()

        return {
            "message": "Now tracking consultation",
            "id": str(consultation_id),
            "initiative_id": consultation.initiative_id,
            "title": consultation.title[:100]
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to track consultation {consultation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to track consultation")


@router.delete(
    "/{consultation_id}/track",
    summary="Untrack a consultation"
)
async def untrack_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stop tracking a consultation."""
    check_yellow_tier(current_user)

    try:
        track = db.query(UserConsultationTrack).filter(
            UserConsultationTrack.user_id == current_user.id,
            UserConsultationTrack.consultation_id == consultation_id
        ).first()

        if not track:
            raise HTTPException(status_code=404, detail="Not tracking this consultation")

        db.delete(track)
        db.commit()

        return {"message": "Stopped tracking consultation", "id": str(consultation_id)}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to untrack consultation {consultation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to untrack consultation")


@router.patch(
    "/{consultation_id}/track",
    summary="Update tracking preferences"
)
async def update_tracking(
    consultation_id: UUID,
    request: UpdateTrackingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update tracking preferences for a consultation."""
    check_yellow_tier(current_user)

    try:
        track = db.query(UserConsultationTrack).filter(
            UserConsultationTrack.user_id == current_user.id,
            UserConsultationTrack.consultation_id == consultation_id
        ).first()

        if not track:
            raise HTTPException(status_code=404, detail="Not tracking this consultation")

        # Update fields
        if request.notify_on_deadline is not None:
            track.notify_on_deadline = request.notify_on_deadline
        if request.notify_on_outcome is not None:
            track.notify_on_outcome = request.notify_on_outcome
        if request.notify_days_before is not None:
            track.notify_days_before = request.notify_days_before
        if request.submission_status is not None:
            track.submission_status = SubmissionStatusEnum(request.submission_status.value)
        if request.notes is not None:
            track.notes = request.notes
        if request.priority is not None:
            track.priority = request.priority

        db.commit()

        return {"message": "Tracking preferences updated", "id": str(consultation_id)}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update tracking for {consultation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update tracking")


# ============================================================================
# AI Analysis (Yellow+ tier)
# ============================================================================

@router.get(
    "/{consultation_id}/analysis",
    response_model=AnalysisResponse,
    summary="Get AI analysis of a consultation"
)
async def get_consultation_analysis(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AnalysisResponse:
    """
    Get AI-powered analysis of a consultation.

    Yellow+ tier required.

    The analysis includes:
    - Executive summary
    - Key questions being asked
    - Stakeholder categories targeted
    - Submission requirements
    - Related legislation context
    - Recommended focus areas
    """
    check_yellow_tier(current_user)

    try:
        consultation = db.query(PublicConsultation).filter(
            PublicConsultation.id == consultation_id
        ).first()

        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")

        # Get the analyser and run analysis
        from services.ai.consultation_analyser import get_consultation_analyser

        analyser = get_consultation_analyser()
        analysis = await analyser.analyse_consultation(consultation)

        return AnalysisResponse(
            consultation_id=consultation.id,
            executive_summary=analysis.executive_summary,
            key_questions=analysis.key_questions,
            stakeholder_categories=analysis.stakeholder_categories,
            submission_requirements=analysis.submission_requirements,
            legislation_context=analysis.legislation_context,
            key_provisions_under_review=analysis.key_provisions_under_review,
            potential_impacts=analysis.potential_impacts,
            recommended_focus_areas=analysis.recommended_focus_areas,
            confidence_score=analysis.confidence_score,
            generated_at=analysis.generated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis for {consultation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ============================================================================
# AI Proposals (Blue tier only)
# ============================================================================

@router.post(
    "/{consultation_id}/proposals",
    response_model=ProposalsResponse,
    summary="Generate AI proposals (Blue tier)"
)
async def generate_proposals(
    consultation_id: UUID,
    request: GenerateProposalsRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ProposalsResponse:
    """
    Generate AI-powered response proposals for a consultation.

    Blue tier only.

    The proposals are personalised based on:
    - User's uploaded documents
    - User profile and interests
    - Consultation analysis
    """
    check_blue_tier(current_user)

    try:
        consultation = db.query(PublicConsultation).filter(
            PublicConsultation.id == consultation_id
        ).first()

        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")

        # Get user documents if specified
        user_documents = []
        if request and request.document_ids:
            from models.user_document import UserDocument
            user_documents = db.query(UserDocument).filter(
                UserDocument.id.in_(request.document_ids),
                UserDocument.user_id == current_user.id
            ).all()

        # First get analysis
        from services.ai.consultation_analyser import get_consultation_analyser
        from services.ai.consultation_proposal_generator import get_consultation_proposal_generator

        analyser = get_consultation_analyser()
        analysis = await analyser.analyse_consultation(consultation)

        # Then generate proposals
        generator = get_consultation_proposal_generator()
        proposal_set = await generator.generate_proposals(
            consultation=consultation,
            analysis=analysis,
            user=current_user,
            user_documents=user_documents,
        )

        return ProposalsResponse(
            consultation_id=consultation.id,
            overall_strategy=proposal_set.overall_strategy,
            recommended_tone=proposal_set.recommended_tone,
            key_messages=proposal_set.key_messages,
            proposals=[
                ProposalItemResponse(
                    id=p.id,
                    question_addressed=p.question_addressed,
                    proposed_response=p.proposed_response,
                    supporting_arguments=p.supporting_arguments,
                    evidence_citations=p.evidence_citations,
                    source_documents=p.source_documents,
                    tone_suggestion=p.tone_suggestion,
                    confidence_score=p.confidence_score,
                )
                for p in proposal_set.proposals
            ],
            tokens_used=proposal_set.tokens_used,
            generated_at=proposal_set.generated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate proposals for {consultation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Proposal generation failed: {str(e)}")


@router.post(
    "/{consultation_id}/proposals/refine",
    response_model=ProposalItemResponse,
    summary="Refine a proposal (Blue tier)"
)
async def refine_proposal(
    consultation_id: UUID,
    request: RefineProposalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ProposalItemResponse:
    """
    Refine a specific proposal based on user feedback.

    Blue tier only.
    """
    check_blue_tier(current_user)

    try:
        consultation = db.query(PublicConsultation).filter(
            PublicConsultation.id == consultation_id
        ).first()

        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")

        from services.ai.consultation_proposal_generator import (
            get_consultation_proposal_generator,
            ConsultationProposal
        )

        # Create a minimal proposal to refine
        # In a real implementation, this would load from saved proposals
        original_proposal = ConsultationProposal(
            id=request.proposal_id,
            question_addressed="Original question",
            proposed_response="Original response",
            supporting_arguments=[],
            evidence_citations=[],
            source_documents=[],
            tone_suggestion="constructive",
            confidence_score=0.7,
        )

        generator = get_consultation_proposal_generator()
        refined = await generator.refine_proposal(
            proposal=original_proposal,
            user_feedback=request.user_feedback,
            consultation=consultation,
        )

        return ProposalItemResponse(
            id=refined.id,
            question_addressed=refined.question_addressed,
            proposed_response=refined.proposed_response,
            supporting_arguments=refined.supporting_arguments,
            evidence_citations=refined.evidence_citations,
            source_documents=refined.source_documents,
            tone_suggestion=refined.tone_suggestion,
            confidence_score=refined.confidence_score,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refine proposal for {consultation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Proposal refinement failed: {str(e)}")




