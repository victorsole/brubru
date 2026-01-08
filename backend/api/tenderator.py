"""
Tenderator API Router

FastAPI endpoints for EU public procurement tender monitoring.
Blue-tier feature for SME users.

Endpoints:
- GET /api/tenders - Search tenders
- GET /api/tenders/{id} - Get tender details
- GET /api/tenders/matches - Get user's matched tenders
- POST /api/tenders/profile - Create/update tender profile
- GET /api/tenders/profile - Get user's tender profile
- POST /api/tenders/matches/{id}/save - Save a match
- POST /api/tenders/matches/{id}/dismiss - Dismiss a match
- POST /api/tenders/fetch - Trigger tender fetch (admin)
- GET /api/tenders/statistics - Get tender statistics
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID

from ..core.database import get_db
from ..models.user import User
from ..models.tender import Tender, TenderProfile, TenderMatch, TenderFetchJob
from ..services.tenders.tender_service import TenderService
from ..services.tenders.matcher import TenderMatcher
from ..schemas.tender_schemas import (
    TenderSummary, TenderDetail,
    TenderProfileCreate, TenderProfileUpdate, TenderProfileResponse,
    TenderMatchResponse, TenderMatchWithTender, TenderMatchUpdate,
    TenderSearchParams, TenderSearchResponse,
    TenderMatchListParams, TenderMatchListResponse,
    TenderFetchRequest, TenderFetchJobResponse,
    TenderStatistics, UserTenderStatistics
)
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tenders",
    tags=["Tenderator"],
    responses={404: {"description": "Not found"}}
)


# ============================================================================
# Dependencies
# ============================================================================

def get_tender_service(db: Session = Depends(get_db)) -> TenderService:
    """Get TenderService instance"""
    return TenderService(db)


def run_profile_matching_background(profile_id: int):
    """
    Run matching for a specific profile as a background task.

    Creates its own database session to avoid transaction conflicts
    with the main request. This is the correct pattern for FastAPI
    BackgroundTasks that need database access.
    """
    import asyncio
    from ..core.database import SessionLocal

    db = SessionLocal()
    try:
        # Create matcher with appropriate threshold
        matcher = TenderMatcher(db, score_threshold=35.0)

        # Run async matching in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(matcher.match_single_profile(profile_id))
        finally:
            loop.close()

        # Create matches in database with duplicate check
        matches_created = 0
        for result in results:
            # Check if match already exists (prevents race conditions)
            existing = db.query(TenderMatch).filter(
                TenderMatch.profile_id == result.profile_id,
                TenderMatch.tender_id == result.tender_id
            ).first()

            if existing:
                continue

            match = TenderMatch(
                tender_id=result.tender_id,
                profile_id=result.profile_id,
                user_id=result.user_id,
                match_score=result.total_score,
                match_reasons=result.score_breakdown,
                match_details=result.match_details,
                created_at=datetime.utcnow()
            )
            db.add(match)
            matches_created += 1

        db.commit()
        logger.info(f"Background matching created {matches_created} matches for profile {profile_id}")
        return matches_created

    except Exception as e:
        logger.error(f"Background matching failed for profile {profile_id}: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


async def require_blue_tier(current_user: User = Depends(get_current_user)) -> User:
    """Require Blue tier subscription for Tenderator access"""
    # Check if user has Blue tier subscription
    if current_user.subscription_tier not in ['blue', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenderator requires Blue tier subscription"
        )
    return current_user


# ============================================================================
# Health Check (must be before /{tender_id})
# ============================================================================

@router.get(
    "/health",
    summary="Health check",
    description="Check Tenderator API health"
)
async def health_check():
    """Tenderator API health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Tenderator API"
    }


# ============================================================================
# Tender Profile Endpoints (Blue Tier) - must be before /{tender_id}
# ============================================================================

@router.get(
    "/profile/me",
    response_model=TenderProfileResponse,
    summary="Get my tender profile",
    description="Get the current user's tender matching profile"
)
async def get_my_profile(
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db)
) -> TenderProfileResponse:
    """
    Get your tender matching profile.

    The profile contains your company information and preferences
    used for matching tenders to your needs.
    """
    try:
        profile = db.query(TenderProfile).filter(
            TenderProfile.user_id == current_user.id
        ).first()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No tender profile found. Create one first."
            )

        return TenderProfileResponse.model_validate(profile)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )


@router.post(
    "/profile",
    response_model=TenderProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tender profile",
    description="Create a new tender matching profile"
)
async def create_profile(
    profile_data: TenderProfileCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db)
) -> TenderProfileResponse:
    """
    Create your tender matching profile.

    **Company Information**:
    - `company_name`: Your company name
    - `company_size`: micro, small, or medium
    - `annual_turnover`: Annual turnover in EUR
    - `employee_count`: Number of employees

    **Preferences**:
    - `cpv_categories`: CPV code prefixes (e.g., ['72', '48'] for IT)
    - `countries_of_interest`: Target countries
    - `max_tender_value`: Maximum contract value
    - `min_deadline_days`: Minimum days until deadline
    """
    try:
        # Check if profile already exists
        existing = db.query(TenderProfile).filter(
            TenderProfile.user_id == current_user.id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Profile already exists. Use PUT to update."
            )

        # Create profile
        profile = TenderProfile(
            user_id=current_user.id,
            **profile_data.model_dump()
        )

        db.add(profile)
        db.commit()
        db.refresh(profile)

        logger.info(f"Created tender profile for user {current_user.id}")

        # Schedule matching to run in background (separate transaction)
        # This ensures profile creation succeeds independently of matching
        background_tasks.add_task(run_profile_matching_background, profile.id)

        return TenderProfileResponse.model_validate(profile)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create profile: {str(e)}"
        )


@router.put(
    "/profile",
    response_model=TenderProfileResponse,
    summary="Update tender profile",
    description="Update your tender matching profile"
)
async def update_profile(
    profile_data: TenderProfileUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db)
) -> TenderProfileResponse:
    """
    Update your tender matching profile.

    Only provided fields will be updated.
    After updating, matches are recalculated automatically.
    """
    try:
        profile = db.query(TenderProfile).filter(
            TenderProfile.user_id == current_user.id
        ).first()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No profile found. Create one first."
            )

        # Update only provided fields
        update_data = profile_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(profile, key, value)

        profile.updated_at = datetime.utcnow()

        # Clear old non-saved matches to recalculate with new profile
        db.query(TenderMatch).filter(
            TenderMatch.profile_id == profile.id,
            TenderMatch.is_saved == False,
            TenderMatch.is_applied == False
        ).delete()

        db.commit()
        db.refresh(profile)

        logger.info(f"Updated tender profile for user {current_user.id}")

        # Schedule matching to run in background (separate transaction)
        # This ensures profile update succeeds independently of matching
        background_tasks.add_task(run_profile_matching_background, profile.id)

        return TenderProfileResponse.model_validate(profile)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


# ============================================================================
# Statistics Endpoints - must be before /{tender_id}
# ============================================================================

@router.get(
    "/statistics",
    response_model=TenderStatistics,
    summary="Get tender statistics",
    description="Get aggregated tender statistics"
)
async def get_statistics(
    db: Session = Depends(get_db)
) -> TenderStatistics:
    """
    Get aggregated tender statistics.

    Available to all users (public tenders data).
    """
    try:
        from datetime import timedelta
        from sqlalchemy import func

        # Total tenders
        total_tenders = db.query(Tender).count()
        open_tenders = db.query(Tender).filter(Tender.status == "open").count()

        # Tenders this week
        week_ago = datetime.utcnow() - timedelta(days=7)
        tenders_this_week = db.query(Tender).filter(
            Tender.publication_date >= week_ago
        ).count()

        # Average value
        avg_value = db.query(func.avg(Tender.estimated_value)).filter(
            Tender.estimated_value.isnot(None)
        ).scalar()

        # By country
        country_counts = db.query(
            Tender.buyer_country,
            func.count(Tender.id)
        ).group_by(Tender.buyer_country).all()

        by_country = {c: count for c, count in country_counts if c}

        # By CPV category (first 2 digits)
        cpv_counts = db.query(
            func.substring(Tender.cpv_main, 1, 2),
            func.count(Tender.id)
        ).filter(Tender.cpv_main.isnot(None)).group_by(
            func.substring(Tender.cpv_main, 1, 2)
        ).all()

        by_cpv = {cpv: count for cpv, count in cpv_counts if cpv}

        # By procedure type
        proc_counts = db.query(
            Tender.procedure_type,
            func.count(Tender.id)
        ).group_by(Tender.procedure_type).all()

        by_procedure = {p: count for p, count in proc_counts if p}

        return TenderStatistics(
            total_tenders=total_tenders,
            open_tenders=open_tenders,
            tenders_this_week=tenders_this_week,
            average_value=avg_value,
            by_country=by_country,
            by_cpv_category=by_cpv,
            by_procedure_type=by_procedure
        )

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


@router.get(
    "/statistics/me",
    response_model=UserTenderStatistics,
    summary="Get my tender statistics",
    description="Get personalized tender statistics"
)
async def get_my_statistics(
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db)
) -> UserTenderStatistics:
    """
    Get your personalized tender statistics.

    Includes match counts, saved tenders, and match score averages.
    """
    try:
        from datetime import timedelta
        from sqlalchemy import func

        user_id = current_user.id

        # Total matches
        total_matches = db.query(TenderMatch).filter(
            TenderMatch.user_id == user_id
        ).count()

        # Saved tenders
        saved_tenders = db.query(TenderMatch).filter(
            TenderMatch.user_id == user_id,
            TenderMatch.is_saved == True
        ).count()

        # Dismissed tenders
        dismissed_tenders = db.query(TenderMatch).filter(
            TenderMatch.user_id == user_id,
            TenderMatch.is_dismissed == True
        ).count()

        # Applied tenders
        applied_tenders = db.query(TenderMatch).filter(
            TenderMatch.user_id == user_id,
            TenderMatch.is_applied == True
        ).count()

        # Average match score
        avg_score = db.query(func.avg(TenderMatch.match_score)).filter(
            TenderMatch.user_id == user_id
        ).scalar()

        # Matches this week
        week_ago = datetime.utcnow() - timedelta(days=7)
        matches_this_week = db.query(TenderMatch).filter(
            TenderMatch.user_id == user_id,
            TenderMatch.created_at >= week_ago
        ).count()

        return UserTenderStatistics(
            total_matches=total_matches,
            saved_tenders=saved_tenders,
            dismissed_tenders=dismissed_tenders,
            applied_tenders=applied_tenders,
            average_match_score=avg_score,
            matches_this_week=matches_this_week
        )

    except Exception as e:
        logger.error(f"Failed to get user statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


# ============================================================================
# Tender Match Endpoints (Blue Tier) - must be before /{tender_id}
# ============================================================================

@router.get(
    "/matches",
    response_model=TenderMatchListResponse,
    summary="Get my tender matches",
    description="Get tenders matched to your profile"
)
async def get_my_matches(
    include_dismissed: bool = Query(False, description="Include dismissed matches"),
    saved_only: bool = Query(False, description="Only show saved matches"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum match score"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    current_user: User = Depends(require_blue_tier),
    service: TenderService = Depends(get_tender_service),
    db: Session = Depends(get_db)
) -> TenderMatchListResponse:
    """
    Get tenders matched to your profile.

    **Filters**:
    - `saved_only`: Only show saved matches
    - `min_score`: Filter by minimum match score (0-100)
    - `include_dismissed`: Include previously dismissed matches
    """
    try:
        matches = service.get_user_matches(
            user_id=str(current_user.id),
            include_dismissed=include_dismissed,
            saved_only=saved_only,
            limit=page_size,
            offset=(page - 1) * page_size
        )

        # Filter by minimum score if specified
        if min_score is not None:
            matches = [m for m in matches if m.match_score >= min_score]

        # Get total count
        total_query = db.query(TenderMatch).filter(
            TenderMatch.user_id == current_user.id
        )
        if not include_dismissed:
            total_query = total_query.filter(TenderMatch.is_dismissed == False)
        if saved_only:
            total_query = total_query.filter(TenderMatch.is_saved == True)
        total = total_query.count()

        # Build response with tender details
        match_responses = []
        for match in matches:
            tender = service.get_tender(match.tender_id)
            if tender:
                match_resp = TenderMatchWithTender(
                    id=match.id,
                    tender_id=match.tender_id,
                    user_id=match.user_id,
                    match_score=match.match_score,
                    match_reasons=match.match_reasons,
                    match_details=match.match_details,
                    is_viewed=match.is_viewed,
                    is_saved=match.is_saved,
                    is_dismissed=match.is_dismissed,
                    is_applied=match.is_applied,
                    user_notes=match.user_notes,
                    user_rating=match.user_rating,
                    notified_at=match.notified_at,
                    created_at=match.created_at,
                    tender=TenderSummary.model_validate(tender)
                )
                match_responses.append(match_resp)

        return TenderMatchListResponse(
            matches=match_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size if total > 0 else 0
        )

    except Exception as e:
        logger.error(f"Failed to get matches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get matches: {str(e)}"
        )


# ============================================================================
# Admin Endpoints - must be before /{tender_id}
# ============================================================================

@router.post(
    "/fetch",
    response_model=TenderFetchJobResponse,
    summary="Fetch new tenders",
    description="Trigger a tender fetch from TED (admin only)"
)
async def fetch_tenders(
    request: TenderFetchRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    service: TenderService = Depends(get_tender_service)
) -> TenderFetchJobResponse:
    """
    Trigger a new tender fetch from TED.

    **Admin only** - Fetches tenders from TED API or SPARQL endpoint.

    **Parameters**:
    - `days_back`: Number of days to look back (1-90)
    - `countries`: Optional country filter
    - `cpv_codes`: Optional CPV code filter
    - `max_value`: Maximum tender value for SME filtering
    - `source`: Data source (ted_api or ted_sparql)
    """
    # Check admin status
    if current_user.subscription_tier != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        # Start fetch in background
        job = await service.fetch_new_tenders(
            days_back=request.days_back,
            countries=request.countries,
            cpv_codes=request.cpv_codes,
            max_value=request.max_value,
            source=request.source
        )

        return TenderFetchJobResponse.model_validate(job)

    except Exception as e:
        logger.error(f"Tender fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fetch failed: {str(e)}"
        )


@router.post(
    "/match",
    summary="Run tender matching",
    description="Run matching algorithm for all users (admin only)"
)
async def run_matching(
    current_user: User = Depends(get_current_user),
    service: TenderService = Depends(get_tender_service)
):
    """
    Run tender matching algorithm.

    **Admin only** - Matches open tenders to all active user profiles.
    """
    if current_user.subscription_tier != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        matches_created = await service.match_tenders_to_users()

        return {
            "message": "Matching completed",
            "matches_created": matches_created
        }

    except Exception as e:
        logger.error(f"Matching failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Matching failed: {str(e)}"
        )


@router.post(
    "/score-sme",
    summary="Batch SME scoring",
    description="Calculate SME scores for tenders (admin only)"
)
async def batch_sme_scoring(
    recalculate: bool = Query(False, description="Recalculate all scores"),
    current_user: User = Depends(get_current_user),
    service: TenderService = Depends(get_tender_service)
):
    """
    Calculate SME suitability scores for tenders.

    **Admin only** - Batch calculate SME scores for:
    - All unscored tenders (default)
    - All tenders (when recalculate=true)
    """
    if current_user.subscription_tier != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        scored_count = service.batch_score_sme_suitability(recalculate=recalculate)

        return {
            "message": "SME scoring completed",
            "tenders_scored": scored_count
        }

    except Exception as e:
        logger.error(f"SME scoring failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SME scoring failed: {str(e)}"
        )


# ============================================================================
# Publication Number Route - must be before /{tender_id}
# ============================================================================

@router.get(
    "/publication/{publication_number}",
    response_model=TenderDetail,
    summary="Get tender by publication number",
    description="Get tender by TED publication number"
)
async def get_tender_by_publication(
    publication_number: str,
    service: TenderService = Depends(get_tender_service)
) -> TenderDetail:
    """
    Get tender by TED publication number (e.g., '1776-2025').
    """
    try:
        tender = service.get_tender_by_publication(publication_number)

        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {publication_number} not found"
            )

        return TenderDetail.model_validate(tender)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tender {publication_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tender: {str(e)}"
        )


# ============================================================================
# EU Procurement Law Integration - must be before /{tender_id}
# ============================================================================

@router.get(
    "/legal-framework",
    summary="Get EU procurement legal framework",
    description="Get relevant EU laws for public procurement"
)
async def get_procurement_legal_framework(
    sector: Optional[str] = None,
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db)
):
    """
    Get EU procurement directives and regulations relevant to tenders.

    Query Parameters:
    - sector: Filter by sector (utilities, defence, concessions, general)

    Returns key EU procurement laws with their requirements.
    """
    from ..services.eu_law_search import EULawSearchService

    try:
        search_service = EULawSearchService(db)

        # Core EU procurement CELEX numbers
        procurement_laws = {
            'general': [
                '32014L0024',  # Public Procurement Directive
                '32014L0025',  # Utilities Directive
            ],
            'utilities': [
                '32014L0025',  # Utilities Directive
            ],
            'defence': [
                '32009L0081',  # Defence Procurement Directive
            ],
            'concessions': [
                '32014L0023',  # Concessions Directive
            ],
            'remedies': [
                '32007L0066',  # Remedies Directive
                '31989L0665',  # Review Procedures Directive
            ],
            'eforms': [
                '32019R1780',  # eForms Regulation
            ],
        }

        # Select relevant laws
        if sector and sector in procurement_laws:
            celex_list = procurement_laws[sector]
        else:
            # Return all core procurement laws
            celex_list = list(set(
                procurement_laws['general'] +
                procurement_laws['remedies'] +
                procurement_laws['eforms']
            ))

        # Fetch law details
        laws = []
        for celex in celex_list:
            result = search_service.get_by_celex(celex)
            if result:
                laws.append(result.to_dict())

        # Also search for recent procurement-related laws
        recent = search_service.search(
            query='public procurement',
            doc_type='Regulation',
            year_from=2020,
            limit=5
        )

        return {
            'core_laws': laws,
            'recent_updates': [r.to_dict() for r in recent.results],
            'sector': sector or 'all',
            'total_core': len(laws),
        }

    except Exception as e:
        logger.error(f"Error getting procurement legal framework: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve legal framework: {str(e)}"
        )


# ============================================================================
# Tender Search Endpoints
# ============================================================================

@router.get(
    "",
    response_model=TenderSearchResponse,
    summary="Search tenders",
    description="Search EU procurement tenders with filters"
)
async def search_tenders(
    query: Optional[str] = Query(None, description="Text search query"),
    countries: Optional[str] = Query(None, description="Comma-separated country codes (e.g., 'BE,FR,DE')"),
    cpv_codes: Optional[str] = Query(None, description="Comma-separated CPV codes"),
    min_value: Optional[float] = Query(None, ge=0, description="Minimum estimated value in EUR"),
    max_value: Optional[float] = Query(None, ge=0, description="Maximum estimated value in EUR"),
    procedure_type: Optional[str] = Query(None, description="Procedure type filter"),
    status: str = Query("open", description="Tender status (open, closed, awarded)"),
    sme_friendly: bool = Query(False, description="Filter for SME-friendly tenders"),
    sort_by: str = Query("publication_date", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    db: Session = Depends(get_db)
) -> TenderSearchResponse:
    """
    Search EU procurement tenders.

    **Filters**:
    - `countries`: ISO 3166-1 alpha-2 codes (BE, FR, DE, etc.)
    - `cpv_codes`: Common Procurement Vocabulary codes
    - `procedure_type`: open, restricted, negotiated, competitive-dialogue
    - `sme_friendly`: Filters for smaller, more accessible tenders

    **Pagination**: Use page and page_size parameters
    """
    try:
        service = TenderService(db)

        # Parse comma-separated values
        country_list = countries.split(",") if countries else None
        cpv_list = cpv_codes.split(",") if cpv_codes else None

        # Search tenders
        tenders = service.search_tenders(
            query=query,
            countries=country_list,
            cpv_codes=cpv_list,
            min_value=min_value,
            max_value=max_value,
            status=status,
            limit=page_size,
            offset=(page - 1) * page_size
        )

        # Get total count for pagination
        total_query = db.query(Tender)
        if status:
            total_query = total_query.filter(Tender.status == status)
        if country_list:
            total_query = total_query.filter(Tender.buyer_country.in_(country_list))
        total = total_query.count()

        return TenderSearchResponse(
            tenders=[TenderSummary.model_validate(t) for t in tenders],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size if total > 0 else 0
        )

    except Exception as e:
        logger.error(f"Tender search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get(
    "/{tender_id}",
    response_model=TenderDetail,
    summary="Get tender details",
    description="Get full details for a specific tender"
)
async def get_tender(
    tender_id: int,
    fetch_xml: bool = Query(False, description="Fetch and parse XML for full details"),
    service: TenderService = Depends(get_tender_service)
) -> TenderDetail:
    """
    Get detailed tender information.

    Set `fetch_xml=true` to fetch and parse the full XML from TED
    for complete tender details (may be slower).
    """
    try:
        tender = service.get_tender(tender_id)

        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {tender_id} not found"
            )

        # Optionally fetch full XML
        if fetch_xml and tender.publication_number:
            tender = await service.fetch_and_parse_xml(tender.publication_number)

        return TenderDetail.model_validate(tender)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tender {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tender: {str(e)}"
        )


@router.get(
    "/{tender_id}/sme-score",
    summary="Get SME suitability score",
    description="Get personalized SME suitability score for a tender"
)
async def get_sme_score(
    tender_id: int,
    company_size: str = Query("small", description="Company size: micro, small, or medium"),
    annual_turnover: Optional[float] = Query(None, description="Annual turnover in EUR"),
    service: TenderService = Depends(get_tender_service)
):
    """
    Get personalized SME suitability score for a tender.

    **Score Range**: 0-100 (higher = more SME-friendly)

    **Scoring Criteria**:
    - Contract value (smaller = more accessible)
    - Procedure type (open procedures preferred)
    - Time until deadline (more time = better)
    - Lot structure (multiple lots increase chances)
    - Requirements complexity
    - Framework agreement status

    **Company Size**:
    - `micro`: < 10 employees, < €2M turnover
    - `small`: < 50 employees, < €10M turnover
    - `medium`: < 250 employees, < €50M turnover
    """
    try:
        result = service.get_sme_score_for_tender(
            tender_id=tender_id,
            company_size=company_size,
            annual_turnover=annual_turnover
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {tender_id} not found"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get SME score for tender {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get SME score: {str(e)}"
        )


@router.get(
    "/{tender_id}/summary",
    summary="Get AI summary of tender",
    description="Generate an AI-powered summary of the tender"
)
async def get_tender_summary(
    tender_id: int,
    current_user: User = Depends(require_blue_tier),
    service: TenderService = Depends(get_tender_service),
    db: Session = Depends(get_db)
):
    """
    Generate an AI-powered summary of the tender.

    Returns a structured summary with:
    - one_liner: Brief description
    - what: What is being procured
    - who: Who is the contracting authority
    - value: Contract value information
    - deadline: Submission deadline info
    - key_requirements: Main requirements list
    - award_focus: Key award criteria focus
    """
    try:
        tender = service.get_tender(tender_id)

        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {tender_id} not found"
            )

        # Build context from tender
        tender_context = f"""
Title: {tender.title}
Contracting Authority: {tender.official_name}
Country: {tender.buyer_country}
Estimated Value: {tender.estimated_value or 'Not specified'} {tender.estimated_value_currency or 'EUR'}
Procedure Type: {tender.procedure_type or 'Not specified'}
Submission Deadline: {tender.submission_deadline or 'Not specified'}
Description: {tender.description or 'No description available'}
CPV Codes: {', '.join(tender.cpv_codes) if tender.cpv_codes else 'Not specified'}
Lot Count: {tender.lot_count or 1}
Award Criteria: {tender.award_criteria or 'Not specified'}
"""

        prompt = f"""Analyse this EU public procurement tender and provide a structured summary.
Be concise and focus on what a potential bidder needs to know.

Tender Information:
{tender_context}

Provide your response in this exact JSON format:
{{
    "one_liner": "A single sentence describing the opportunity",
    "what": "What is being procured (2-3 sentences max)",
    "who": "Brief description of the contracting authority",
    "value": "Contract value or budget information",
    "deadline": "Submission deadline with any important time notes",
    "key_requirements": ["requirement 1", "requirement 2", "requirement 3"],
    "award_focus": "What the evaluation criteria prioritise"
}}

Respond ONLY with the JSON, no additional text."""

        try:
            from ..services.ai_service import get_ai_service
            import json
            import re

            ai_service = get_ai_service()
            response = await ai_service.chat(
                user_message=prompt,
                conversation_history=None,
                user_id=str(current_user.id)
            )

            # Extract JSON from response with robust parsing
            response_text = response.get("response", "")
            summary = _extract_and_validate_summary_json(response_text)

            if summary:
                return summary
            else:
                # Fallback if AI doesn't return valid JSON
                logger.warning("AI response did not contain valid summary JSON, using fallback")
                return _build_fallback_summary(tender)

        except Exception as ai_error:
            logger.warning(f"AI summary generation failed, using fallback: {ai_error}")
            return _build_fallback_summary(tender)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate summary for tender {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )


def _extract_and_validate_summary_json(response_text: str) -> Optional[dict]:
    """
    Extract and validate JSON summary from AI response.

    Handles edge cases:
    - JSON wrapped in markdown code blocks
    - Multiple JSON objects (takes the first valid one)
    - Malformed JSON with trailing commas
    - Missing required fields

    Returns validated summary dict or None if invalid.
    """
    import json
    import re

    if not response_text:
        return None

    # Required fields for a valid summary
    required_fields = {"one_liner", "what", "who", "value", "deadline", "key_requirements", "award_focus"}

    # Try to extract JSON from various formats
    json_candidates = []

    # Pattern 1: JSON in markdown code block
    code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response_text)
    if code_block_match:
        json_candidates.append(code_block_match.group(1))

    # Pattern 2: Raw JSON object (greedy match for outermost braces)
    # Use a more precise approach: find balanced braces
    brace_depth = 0
    start_idx = None
    for i, char in enumerate(response_text):
        if char == '{':
            if brace_depth == 0:
                start_idx = i
            brace_depth += 1
        elif char == '}':
            brace_depth -= 1
            if brace_depth == 0 and start_idx is not None:
                json_candidates.append(response_text[start_idx:i+1])
                start_idx = None

    # Try each candidate
    for candidate in json_candidates:
        try:
            # Clean up common issues
            cleaned = candidate.strip()
            # Remove trailing commas before } or ]
            cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)

            parsed = json.loads(cleaned)

            # Validate structure
            if not isinstance(parsed, dict):
                continue

            # Check required fields
            if required_fields.issubset(parsed.keys()):
                # Validate types
                if (isinstance(parsed.get("key_requirements"), list) and
                    isinstance(parsed.get("one_liner"), str) and
                    isinstance(parsed.get("what"), str)):
                    return parsed

        except json.JSONDecodeError:
            continue

    return None


def _build_fallback_summary(tender) -> dict:
    """Build a basic summary from tender data when AI fails."""
    # Safely format value
    if tender.estimated_value:
        currency = tender.estimated_value_currency or 'EUR'
        value_str = f"{tender.estimated_value:,.0f} {currency}"
    else:
        value_str = "Not specified"

    # Safely format deadline
    if tender.submission_deadline:
        try:
            deadline_str = tender.submission_deadline.strftime("%d %B %Y")
        except (AttributeError, ValueError):
            deadline_str = "Check tender notice"
    else:
        deadline_str = "Check tender notice"

    # Safely truncate description
    if tender.description and len(tender.description) > 300:
        what_str = tender.description[:300] + "..."
    elif tender.description:
        what_str = tender.description
    else:
        what_str = "See tender notice for details."

    return {
        "one_liner": tender.title or "EU public procurement opportunity",
        "what": what_str,
        "who": tender.official_name or "EU contracting authority",
        "value": value_str,
        "deadline": deadline_str,
        "key_requirements": ["Review full tender documentation"],
        "award_focus": "Refer to tender evaluation criteria"
    }


# ============================================================================
# Match Actions - these routes are specific enough they work after /{tender_id}
# ============================================================================

@router.post(
    "/matches/{match_id}/save",
    response_model=TenderMatchResponse,
    summary="Save a match",
    description="Save a tender match for later"
)
async def save_match(
    match_id: int,
    current_user: User = Depends(require_blue_tier),
    service: TenderService = Depends(get_tender_service)
) -> TenderMatchResponse:
    """
    Save a tender match to your saved list.
    """
    try:
        match = service.save_match(match_id, str(current_user.id))

        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Match {match_id} not found"
            )

        return TenderMatchResponse.model_validate(match)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save match {match_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save match: {str(e)}"
        )


@router.post(
    "/matches/{match_id}/dismiss",
    response_model=TenderMatchResponse,
    summary="Dismiss a match",
    description="Dismiss a tender match (hide from list)"
)
async def dismiss_match(
    match_id: int,
    current_user: User = Depends(require_blue_tier),
    service: TenderService = Depends(get_tender_service)
) -> TenderMatchResponse:
    """
    Dismiss a tender match so it doesn't appear in your list.
    """
    try:
        match = service.dismiss_match(match_id, str(current_user.id))

        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Match {match_id} not found"
            )

        return TenderMatchResponse.model_validate(match)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to dismiss match {match_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dismiss match: {str(e)}"
        )


@router.put(
    "/matches/{match_id}",
    response_model=TenderMatchResponse,
    summary="Update match",
    description="Update match notes or rating"
)
async def update_match(
    match_id: int,
    update_data: TenderMatchUpdate,
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db)
) -> TenderMatchResponse:
    """
    Update match details (notes, rating, applied status).
    """
    try:
        match = db.query(TenderMatch).filter(
            TenderMatch.id == match_id,
            TenderMatch.user_id == current_user.id
        ).first()

        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Match {match_id} not found"
            )

        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(match, key, value)

        match.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(match)

        return TenderMatchResponse.model_validate(match)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update match {match_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update match: {str(e)}"
        )


@router.get(
    "/{tender_id}/legal-requirements",
    summary="Get legal requirements for tender",
    description="Get applicable EU law requirements for a specific tender"
)
async def get_tender_legal_requirements(
    tender_id: int,
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db)
):
    """
    Get EU legal requirements applicable to a specific tender.

    Based on tender type, value, and sector, returns:
    - Applicable directives
    - Key compliance requirements
    - Threshold information
    """
    from ..services.eu_law_search import EULawSearchService

    try:
        # Get tender
        tender = db.query(Tender).filter(Tender.id == tender_id).first()
        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {tender_id} not found"
            )

        search_service = EULawSearchService(db)

        # Determine applicable directive based on tender type
        applicable_laws = []

        # Check tender value against EU thresholds (2024 values)
        thresholds = {
            'supplies_services_central': 143000,
            'supplies_services_sub_central': 221000,
            'works': 5538000,
            'utilities': 443000,
            'defence': 443000,
        }

        # Get Public Procurement Directive
        ppd = search_service.get_by_celex('32014L0024')
        if ppd:
            applicable_laws.append({
                **ppd.to_dict(),
                'relevance': 'Primary directive for public contracts'
            })

        # Search for sector-specific laws if tender has CPV codes
        if tender.cpv_codes:
            cpv_main = tender.cpv_codes[0][:2] if tender.cpv_codes else None

            # Map CPV to sectors
            sector_cpv = {
                '09': 'energy',
                '50': 'transport',
                '60': 'transport',
                '64': 'postal',
                '65': 'utilities',
            }

            if cpv_main in sector_cpv:
                utilities = search_service.get_by_celex('32014L0025')
                if utilities:
                    applicable_laws.append({
                        **utilities.to_dict(),
                        'relevance': f'Utilities directive for {sector_cpv[cpv_main]} sector'
                    })

        return {
            'tender_id': str(tender_id),
            'tender_title': tender.title,
            'estimated_value': tender.estimated_value,
            'applicable_laws': applicable_laws,
            'thresholds': thresholds,
            'note': 'Thresholds are 2024 values in EUR, excluding VAT'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tender legal requirements: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve legal requirements: {str(e)}"
        )

