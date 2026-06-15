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
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID

from core.database import get_db
from models.user import User
from models.tender import Tender, TenderProfile, TenderMatch, TenderFetchJob
from services.tenders.tender_service import TenderService
from services.tenders.matcher import TenderMatcher
from schemas.tender_schemas import (
    TenderSummary, TenderDetail,
    TenderProfileCreate, TenderProfileUpdate, TenderProfileResponse,
    TenderMatchResponse, TenderMatchWithTender, TenderMatchUpdate,
    TenderSearchParams, TenderSearchResponse,
    TenderMatchListParams, TenderMatchListResponse,
    TenderFetchRequest, TenderFetchJobResponse,
    TenderStatistics, UserTenderStatistics
)
from .auth import get_current_user
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import cpv_for_interests, keywords_for_interests

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
    from core.database import SessionLocal

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


@router.get(
    "/profile/suggested-from-interests",
    summary="Suggested tender profile from your Policy Interests",
    description=(
        "**What it does**\nTurns your My EU Bubble Policy Interests into a head-start "
        "tender profile: the CPV procurement categories and keywords that match your "
        "areas, so you can pre-fill the profile form instead of starting blank.\n\n"
        "**When to use it**\nThe 'Use my policy interests' button on the tender-profile form.\n\n"
        "**You get back**\n`cpv_categories` (CPV divisions) + `keywords`, both derived "
        "from your interests. Non-destructive — you edit and save."),
)
async def suggested_profile_from_interests(
    current_user: User = Depends(require_blue_tier),
):
    interests = _interest_list(current_user)
    return {
        "interests": interests,
        "cpv_categories": sorted(cpv_for_interests(interests)),
        "keywords": sorted(keywords_for_interests(interests)),
    }


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
# Unified calendar deadlines (TED + F&T proposals + F&T tenders)
# ============================================================================

@router.get(
    "/calendar-deadlines",
    summary="Unified deadlines feed for the Tenderator calendar",
    description=(
        "Returns submission/application deadlines from all three live "
        "sources (TED tenders, F&T calls for proposals, F&T calls for "
        "tenders) in a single shape so the calendar widget can render "
        "any source on the right day. Blue tier only."
    ),
)
async def get_calendar_deadlines(
    months_ahead: int = Query(6, ge=1, le=12, description="How many months ahead to include"),
    only_open: bool = Query(True, description="When true, exclude already-closed items"),
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    from datetime import timedelta
    from models.funding_tenders import FtCallForProposals, FtCallForTenders

    now = datetime.utcnow()
    horizon = now + timedelta(days=30 * months_ahead)
    items: List[Dict[str, Any]] = []

    # --- TED ---
    try:
        qry = db.query(Tender).filter(Tender.submission_deadline != None)  # noqa: E711
        if only_open:
            qry = qry.filter(Tender.submission_deadline >= now)
        qry = qry.filter(Tender.submission_deadline <= horizon)
        for t in qry.order_by(Tender.submission_deadline.asc()).limit(500).all():
            items.append({
                "id": f"ted:{t.id}",
                "source": "ted",
                "ref": t.publication_number,
                "title": t.title,
                "deadline": t.submission_deadline.isoformat() if t.submission_deadline else None,
                "budget": float(t.estimated_value) if t.estimated_value else None,
                "currency": getattr(t, "estimated_value_currency", None) or "EUR",
                "country": t.buyer_country,
                "programme": None,
                "source_url": getattr(t, "ted_url", None) or "",
            })
    except Exception as exc:
        logger.warning(f"calendar TED query failed: {exc}")
        db.rollback()

    # --- F&T proposals ---
    try:
        qry = db.query(FtCallForProposals).filter(
            FtCallForProposals.is_test == False,  # noqa: E712
            FtCallForProposals.deadline != None,  # noqa: E711
        )
        if only_open:
            qry = qry.filter(FtCallForProposals.deadline >= now)
        qry = qry.filter(FtCallForProposals.deadline <= horizon)
        for p in qry.order_by(FtCallForProposals.deadline.asc()).limit(500).all():
            items.append({
                "id": f"ft_proposals:{p.id}",
                "source": "ft_proposals",
                "ref": p.topic_id,
                "title": p.title,
                "deadline": p.deadline.isoformat() if p.deadline else None,
                "budget": float(p.indicative_budget) if p.indicative_budget else None,
                "currency": p.budget_currency or "EUR",
                "country": None,
                "programme": p.framework_programme,
                "source_url": p.source_url,
            })
    except Exception as exc:
        logger.warning(f"calendar F&T proposals query failed: {exc}")
        db.rollback()

    # --- F&T tenders ---
    try:
        qry = db.query(FtCallForTenders).filter(
            FtCallForTenders.is_test == False,  # noqa: E712
            FtCallForTenders.deadline != None,  # noqa: E711
        )
        if only_open:
            qry = qry.filter(FtCallForTenders.deadline >= now)
        qry = qry.filter(FtCallForTenders.deadline <= horizon)
        for ftt in qry.order_by(FtCallForTenders.deadline.asc()).limit(500).all():
            items.append({
                "id": f"ft_tenders:{ftt.id}",
                "source": "ft_tenders",
                "ref": ftt.tender_reference,
                "title": ftt.title,
                "deadline": ftt.deadline.isoformat() if ftt.deadline else None,
                "budget": float(ftt.estimated_value) if ftt.estimated_value else None,
                "currency": ftt.value_currency or "EUR",
                "country": None,
                "programme": None,
                "source_url": ftt.source_url,
            })
    except Exception as exc:
        logger.warning(f"calendar F&T tenders query failed: {exc}")
        db.rollback()

    # --- F&T Portal events (info days, webinars, programme events) -----
    # economy_items(body_code='ftportal', item_type='event'); document_date is
    # the event start date so a "deadline >= now" filter == "upcoming events".
    try:
        rows = db.execute(
            text(
                "SELECT id, title, document_date, public_url "
                "FROM economy_items "
                "WHERE body_code = 'ftportal' AND item_type = 'event' "
                "  AND document_date IS NOT NULL "
                "  AND document_date <= :horizon "
                + ("AND document_date >= :now " if only_open else "")
                + "ORDER BY document_date ASC LIMIT 200"
            ),
            {"horizon": horizon, "now": now} if only_open else {"horizon": horizon},
        ).fetchall()
        for r in rows:
            items.append({
                "id": f"ft_events:{r.id}",
                "source": "ft_events",
                "ref": None,
                "title": r.title,
                "deadline": r.document_date.isoformat() if r.document_date else None,
                "budget": None,
                "currency": "EUR",
                "country": None,
                "programme": "Info day / event",
                "source_url": r.public_url,
            })
    except Exception as exc:
        logger.warning(f"calendar F&T events query failed: {exc}")
        db.rollback()

    # Sort by deadline ascending for the frontend
    items.sort(key=lambda x: x.get("deadline") or "9999-12-31")

    return {
        "months_ahead": months_ahead,
        "only_open": only_open,
        "total": len(items),
        "by_source": {
            "ted": sum(1 for i in items if i["source"] == "ted"),
            "ft_proposals": sum(1 for i in items if i["source"] == "ft_proposals"),
            "ft_tenders": sum(1 for i in items if i["source"] == "ft_tenders"),
            "ft_events": sum(1 for i in items if i["source"] == "ft_events"),
        },
        "items": items,
        "generated_at": now.isoformat(),
    }


# ============================================================================
# F&T Portal activity sidebar (news + upcoming events)
# ============================================================================

@router.get(
    "/portal-activity",
    summary="EU Funding & Tenders Portal news + upcoming events",
    description=(
        "Returns the latest news items and the next upcoming events from the "
        "EU Funding & Tenders Portal feeds (economy_items body_code='ftportal'). "
        "Feeds the right-rail PortalActivityPanel on the Tenderator dashboard. "
        "News is sorted by document_date desc; events are sorted by document_date "
        "asc and restricted to upcoming when only_upcoming=true (default). "
        "Blue tier only."
    ),
)
async def get_portal_activity(
    news_limit: int = Query(5, ge=1, le=25, description="Latest news items to return"),
    events_limit: int = Query(5, ge=1, le=25, description="Upcoming events to return"),
    only_upcoming: bool = Query(True, description="When true, exclude past events"),
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    news_items: List[Dict[str, Any]] = []
    event_items: List[Dict[str, Any]] = []

    try:
        rows = db.execute(
            text(
                "SELECT id, title, summary, document_date, public_url "
                "FROM economy_items "
                "WHERE body_code = 'ftportal' AND item_type = 'news' "
                "ORDER BY document_date DESC NULLS LAST, id DESC LIMIT :lim"
            ),
            {"lim": news_limit},
        ).fetchall()
        for r in rows:
            news_items.append({
                "id": r.id,
                "title": r.title,
                "summary": (r.summary or "")[:200] if r.summary else None,
                "document_date": r.document_date.isoformat() if r.document_date else None,
                "source_url": r.public_url,
            })
    except Exception as exc:
        logger.warning(f"portal-activity news query failed: {exc}")
        db.rollback()

    try:
        params: Dict[str, Any] = {"lim": events_limit}
        where = "body_code = 'ftportal' AND item_type = 'event'"
        if only_upcoming:
            where += " AND (document_date >= :now OR document_date IS NULL)"
            params["now"] = now
        rows = db.execute(
            text(
                f"SELECT id, title, summary, document_date, public_url "
                f"FROM economy_items "
                f"WHERE {where} "
                f"ORDER BY document_date ASC NULLS LAST LIMIT :lim"
            ),
            params,
        ).fetchall()
        for r in rows:
            event_items.append({
                "id": r.id,
                "title": r.title,
                "summary": (r.summary or "")[:200] if r.summary else None,
                "document_date": r.document_date.isoformat() if r.document_date else None,
                "source_url": r.public_url,
            })
    except Exception as exc:
        logger.warning(f"portal-activity events query failed: {exc}")
        db.rollback()

    return {
        "news": news_items,
        "events": event_items,
        "only_upcoming": only_upcoming,
        "generated_at": now.isoformat(),
    }


# ============================================================================
# Phase 5: EU Programmes catalogue
# ============================================================================

@router.get(
    "/programmes",
    summary="EU funding programmes catalogue",
    description=(
        "Returns the list of seeded EU funding programmes (Horizon Europe, "
        "LIFE, CEF, Digital Europe Programme, EU4Health, Erasmus+, EIC, "
        "etc.) with budget, period, and source URL. Blue tier only."
    ),
)
async def list_programmes(
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            text(
                """
                SELECT programme_code, name, parent_framework, budget_total,
                       budget_currency, period_start, period_end, description,
                       source_url
                FROM ft_programmes
                WHERE is_test = FALSE
                ORDER BY
                    CASE parent_framework
                        WHEN 'MFF 2021-2027' THEN 1
                        WHEN 'Horizon Europe pillar' THEN 2
                        WHEN 'MFF 2014-2020' THEN 3
                        WHEN 'MFF 2007-2013' THEN 4
                        ELSE 5
                    END,
                    budget_total DESC NULLS LAST
                """
            )
        ).mappings().all()
    except Exception as exc:
        logger.error(f"programmes query failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Programmes query failed: {exc}")

    items = []
    for r in rows:
        items.append({
            "programme_code": r["programme_code"],
            "name": r["name"],
            "parent_framework": r["parent_framework"],
            "budget_total": float(r["budget_total"]) if r["budget_total"] else None,
            "budget_currency": r["budget_currency"],
            "period_start": r["period_start"].isoformat() if r["period_start"] else None,
            "period_end": r["period_end"].isoformat() if r["period_end"] else None,
            "description": r["description"],
            "source_url": r["source_url"],
        })
    return {"items": items, "total": len(items)}


# Pull text + datetime locally for the SQL above (already imported globally)
from sqlalchemy import text


# ============================================================================
# Phase 3: AI brief + similar-projects endpoints
# ============================================================================

from pydantic import BaseModel as _PydanticBaseModel


class BriefRequest(_PydanticBaseModel):
    """Request body for the AI-generated tender brief."""
    opportunity_id: str  # "ted:123" / "ft_proposals:<uuid>" / "ft_tenders:<uuid>" / "ft_projects:<uuid>"


@router.post(
    "/brief",
    summary="AI-extracted one-page brief for an opportunity",
    description=(
        "Reads the call's body (title + description + objective + scope + "
        "expected_outcome + eligibility) and asks the AI to extract a "
        "structured 7-field brief: scope, eligible_applicants, "
        "budget_per_project, trl_range, key_dates, evaluation_criteria, "
        "first_steps. Returns plain text fields; the frontend renders a "
        "side-by-side card next to the raw description. Blue tier only."
    ),
)
async def generate_opportunity_brief(
    request: BriefRequest,
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    from models.funding_tenders import (
        FtCallForProposals,
        FtCallForTenders,
        FtFundedProject,
    )

    # Resolve opportunity to a body string we can pass to the AI
    try:
        kind, raw_id = request.opportunity_id.split(":", 1)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="opportunity_id must be of the form '<source>:<id>'",
        )

    body_parts: List[str] = []
    title = ""
    programme = ""
    deadline = None

    try:
        if kind == "ted":
            row = db.query(Tender).filter(Tender.id == int(raw_id)).first()
            if not row:
                raise HTTPException(status_code=404, detail="Tender not found")
            title = row.title or ""
            body_parts.append(f"Title: {title}")
            if row.description:
                body_parts.append(f"Description: {row.description}")
            if row.official_name:
                body_parts.append(f"Buyer: {row.official_name}")
            if row.cpv_main:
                body_parts.append(f"CPV main code: {row.cpv_main}")
            deadline = row.submission_deadline.isoformat() if row.submission_deadline else None
        elif kind == "ft_proposals":
            row = db.query(FtCallForProposals).filter(FtCallForProposals.id == raw_id).first()
            if not row:
                raise HTTPException(status_code=404, detail="Call for proposals not found")
            title = row.title or ""
            programme = row.framework_programme or ""
            body_parts.append(f"Title: {title}")
            if row.framework_programme:
                body_parts.append(f"Framework programme: {row.framework_programme}")
            if row.type_of_action:
                body_parts.append(f"Type of action: {row.type_of_action}")
            if row.description:
                body_parts.append(f"Description: {row.description}")
            if row.indicative_budget:
                body_parts.append(f"Indicative budget: {row.indicative_budget} {row.budget_currency or 'EUR'}")
            deadline = row.deadline.isoformat() if row.deadline else None
        elif kind == "ft_tenders":
            row = db.query(FtCallForTenders).filter(FtCallForTenders.id == raw_id).first()
            if not row:
                raise HTTPException(status_code=404, detail="Call for tenders not found")
            title = row.title or ""
            body_parts.append(f"Title: {title}")
            if row.contracting_authority:
                body_parts.append(f"Contracting authority: {row.contracting_authority}")
            if row.contract_type:
                body_parts.append(f"Contract type: {row.contract_type}")
            if row.description:
                body_parts.append(f"Description: {row.description}")
            if row.estimated_value:
                body_parts.append(f"Estimated value: {row.estimated_value} {row.value_currency or 'EUR'}")
            deadline = row.deadline.isoformat() if row.deadline else None
        elif kind == "ft_projects":
            row = db.query(FtFundedProject).filter(FtFundedProject.id == raw_id).first()
            if not row:
                raise HTTPException(status_code=404, detail="Funded project not found")
            title = row.title or ""
            programme = row.framework_programme or ""
            body_parts.append(f"Title: {title}")
            if row.framework_programme:
                body_parts.append(f"Framework programme: {row.framework_programme}")
            if row.type_of_action:
                body_parts.append(f"Type of action: {row.type_of_action}")
            if row.objective:
                body_parts.append(f"Objective: {row.objective}")
            if row.coordinator_name:
                body_parts.append(f"Coordinator: {row.coordinator_name} ({row.coordinator_country or '?'})")
            if row.eu_contribution:
                body_parts.append(f"EU contribution: {row.eu_contribution} {row.cost_currency or 'EUR'}")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown opportunity source: {kind}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"brief resolve failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not resolve opportunity: {exc}")

    if not body_parts:
        raise HTTPException(status_code=422, detail="Opportunity has no body to summarise")

    body_text = "\n\n".join(body_parts)[:8000]

    # Ask the AI service for a structured 7-field brief
    try:
        from services.ai_service import get_ai_service
        ai_service = get_ai_service()
        prompt = (
            "You are summarising one EU funding opportunity for a public-affairs professional. "
            "Read the opportunity body below and extract a 7-field brief. Each field is a single "
            "short sentence. Do NOT invent facts. If a field is not present in the body, write "
            "exactly: 'Not stated in the call.'. Never use em-dashes. Output strict JSON with "
            "these keys and no other text:\n\n"
            "{\n"
            '  "scope": "...",\n'
            '  "eligible_applicants": "...",\n'
            '  "budget_per_project": "...",\n'
            '  "trl_range": "...",\n'
            '  "key_dates": "...",\n'
            '  "evaluation_criteria": "...",\n'
            '  "first_steps": "..."\n'
            "}\n\n"
            "Opportunity body:\n" + body_text
        )
        # Use the non-streaming chat path with minimal context
        response = await ai_service.chat(
            user_message=prompt,
            conversation_history=[],
            user_id=str(current_user.id),
            use_context=False,
            stream=False,
            is_pre_user=False,
        )
        ai_text = response.message
    except Exception as exc:
        logger.error(f"brief AI call failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI brief generation failed: {str(exc)}",
        )

    # Parse the JSON envelope. Fall back to a single-field summary if the
    # model returned unstructured text (the system prompt asks for JSON).
    import json as _json
    import re as _re
    parsed: dict = {}
    try:
        # The model sometimes wraps JSON in a code fence. Strip it.
        cleaned = _re.sub(r"^```(?:json)?\s*|\s*```$", "", ai_text.strip(), flags=_re.MULTILINE)
        parsed = _json.loads(cleaned)
    except Exception:
        parsed = {
            "scope": ai_text.strip()[:300],
            "eligible_applicants": "Not stated in the call.",
            "budget_per_project": "Not stated in the call.",
            "trl_range": "Not stated in the call.",
            "key_dates": "Not stated in the call.",
            "evaluation_criteria": "Not stated in the call.",
            "first_steps": "Not stated in the call.",
        }

    return {
        "opportunity_id": request.opportunity_id,
        "title": title,
        "programme": programme,
        "deadline": deadline,
        "brief": {
            "scope": parsed.get("scope", "Not stated in the call."),
            "eligible_applicants": parsed.get("eligible_applicants", "Not stated in the call."),
            "budget_per_project": parsed.get("budget_per_project", "Not stated in the call."),
            "trl_range": parsed.get("trl_range", "Not stated in the call."),
            "key_dates": parsed.get("key_dates", "Not stated in the call."),
            "evaluation_criteria": parsed.get("evaluation_criteria", "Not stated in the call."),
            "first_steps": parsed.get("first_steps", "Not stated in the call."),
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get(
    "/similar-projects",
    summary="Past grantees on similar calls",
    description=(
        "Returns up to 10 ft_funded_projects that share a framework programme "
        "and/or type_of_action with the requested opportunity. Helps the user "
        "see who has won similar funding so they can map potential consortium "
        "partners. Blue tier only."
    ),
)
async def get_similar_projects(
    opportunity_id: str = Query(..., description="<source>:<id>"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    from models.funding_tenders import (
        FtCallForProposals,
        FtFundedProject,
    )

    try:
        kind, raw_id = opportunity_id.split(":", 1)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="opportunity_id must be of the form '<source>:<id>'",
        )

    programme: Optional[str] = None
    type_of_action: Optional[str] = None
    title_anchor: str = ""

    if kind == "ft_proposals":
        row = db.query(FtCallForProposals).filter(FtCallForProposals.id == raw_id).first()
        if row:
            programme = row.framework_programme
            type_of_action = row.type_of_action
            title_anchor = row.title or ""
    elif kind == "ft_projects":
        row = db.query(FtFundedProject).filter(FtFundedProject.id == raw_id).first()
        if row:
            programme = row.framework_programme
            type_of_action = row.type_of_action
            title_anchor = row.title or ""
    elif kind == "ted":
        # TED tenders have no programme. We return an empty similar list with
        # a hint, rather than 404, so the UI degrades gracefully.
        return {
            "opportunity_id": opportunity_id,
            "anchor": {"programme": None, "type_of_action": None, "title": ""},
            "items": [],
            "note": "TED tenders are not part of the framework-programme pipeline; no similar projects to surface.",
        }
    else:
        # ft_tenders has no programme either; same degradation.
        return {
            "opportunity_id": opportunity_id,
            "anchor": {"programme": None, "type_of_action": None, "title": ""},
            "items": [],
            "note": "This source is not linked to ft_funded_projects.",
        }

    if not programme and not type_of_action:
        return {
            "opportunity_id": opportunity_id,
            "anchor": {"programme": None, "type_of_action": None, "title": title_anchor},
            "items": [],
            "note": "Anchor opportunity has no programme or type_of_action; cannot match.",
        }

    # The two tables store programme + type_of_action under different
    # conventions:
    #   - ft_calls_for_proposals: "2021 - 2027" / "Research and Innovation action"
    #   - ft_funded_projects:     "HORIZON" / "RIA"
    # Map period strings to the project-table codes and expand action names
    # to their canonical abbreviations.
    PROGRAMME_PERIOD_TO_CODES = {
        "2021 - 2027": ["HORIZON"],
        "2014 - 2020": ["H2020", "FP7"],
        "2007 - 2013": ["FP7"],
    }
    TOA_ALIASES = {
        "research and innovation action": "RIA",
        "innovation action": "IA",
        "coordination and support action": "CSA",
    }

    programme_codes = PROGRAMME_PERIOD_TO_CODES.get(programme or "", [programme] if programme else [])
    toa_code = TOA_ALIASES.get((type_of_action or "").lower(), type_of_action)

    qry = db.query(FtFundedProject).filter(FtFundedProject.is_test == False)  # noqa: E712
    if programme_codes:
        qry = qry.filter(FtFundedProject.framework_programme.in_(programme_codes))
    if toa_code:
        qry = qry.filter(FtFundedProject.type_of_action == toa_code)

    # Exclude the anchor row itself when the anchor IS an ft_project
    if kind == "ft_projects":
        qry = qry.filter(FtFundedProject.id != raw_id)

    try:
        rows = (
            qry.order_by(FtFundedProject.start_date.desc().nullslast())
            .limit(limit)
            .all()
        )
    except Exception as exc:
        logger.error(f"similar-projects query failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}")

    items = [
        {
            "id": str(r.id),
            "project_id": r.project_id,
            "acronym": r.project_acronym,
            "title": r.title,
            "objective": (r.objective or "")[:400] if r.objective else None,
            "framework_programme": r.framework_programme,
            "type_of_action": r.type_of_action,
            "coordinator_name": r.coordinator_name,
            "coordinator_country": r.coordinator_country,
            "start_date": r.start_date.isoformat() if r.start_date else None,
            "end_date": r.end_date.isoformat() if r.end_date else None,
            "eu_contribution": float(r.eu_contribution) if r.eu_contribution else None,
            "cost_currency": r.cost_currency or "EUR",
            "source_url": r.source_url,
        }
        for r in rows
    ]

    return {
        "opportunity_id": opportunity_id,
        "anchor": {
            "programme": programme,
            "type_of_action": type_of_action,
            "title": title_anchor,
        },
        "items": items,
    }


# ============================================================================
# Step 6: FTS recipients ("who's won this kind of money before") for the
# drawer evidence block. Reads economy_items (body_code='commission',
# item_type='funding_recipient') — same data the public
# /api/v2/funding/eu-funding-recipients endpoint serves.
# ============================================================================

@router.get(
    "/recipients",
    summary="Past EU funding recipients matching the opportunity's programme/keyword",
    description=(
        "Returns up to 8 EU Financial Transparency System (FTS) recipients "
        "whose programme or subject text overlaps with the opportunity's "
        "programme/title. Surfaces who has won this kind of EU money "
        "before — the Funder's Lens evidence-pack widget. Blue tier only."
    ),
)
async def get_fts_recipients(
    opportunity_id: Optional[str] = Query(None, description="<source>:<id>"),
    programme: Optional[str] = Query(None, description="Free-text programme substring (overrides the one inferred from opportunity_id)."),
    q: Optional[str] = Query(None, description="Free-text overlay on title/summary."),
    limit: int = Query(8, ge=1, le=50),
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    from models.funding_tenders import FtCallForProposals, FtFundedProject

    # Infer a programme + a title-anchor from the opportunity_id if given.
    inferred_programme: Optional[str] = None
    inferred_anchor: str = ""
    if opportunity_id:
        try:
            kind, raw_id = opportunity_id.split(":", 1)
        except ValueError:
            kind, raw_id = "", ""
        if kind == "ft_proposals":
            row = db.query(FtCallForProposals).filter(FtCallForProposals.id == raw_id).first()
            if row:
                inferred_programme = row.framework_programme
                inferred_anchor = row.title or ""
        elif kind == "ft_projects":
            row = db.query(FtFundedProject).filter(FtFundedProject.id == raw_id).first()
            if row:
                inferred_programme = row.framework_programme
                inferred_anchor = row.title or ""

    eff_programme = (programme or inferred_programme or "").strip()
    eff_q = (q or "").strip()

    if not eff_programme and not eff_q:
        # Nothing to anchor on → return an empty list, not 404. The frontend
        # hides the block cleanly when items is empty.
        return {"opportunity_id": opportunity_id, "anchor": {"programme": eff_programme, "title": inferred_anchor}, "items": []}

    where = ["item_type = 'funding_recipient'"]
    params: Dict[str, Any] = {}
    if eff_programme:
        where.append("(summary ILIKE :prog OR title ILIKE :prog)")
        params["prog"] = f"%{eff_programme}%"
    if eff_q:
        where.append("(title ILIKE :q OR summary ILIKE :q)")
        params["q"] = f"%{eff_q}%"
    params["limit"] = limit

    try:
        rows = db.execute(
            text(
                "SELECT id, body_code, title, summary, public_url, document_date "
                "FROM economy_items WHERE " + " AND ".join(where) + " "
                "ORDER BY document_date DESC NULLS LAST, id DESC LIMIT :limit"
            ),
            params,
        ).fetchall()
    except Exception as exc:
        logger.warning("get_fts_recipients failed: %s", exc)
        db.rollback()
        rows = []

    items = [
        {
            "id": r.id,
            "title": r.title,
            "summary": (r.summary or "")[:240] if r.summary else None,
            "source_url": r.public_url,
            "document_date": r.document_date.isoformat() if r.document_date else None,
        }
        for r in rows
    ]
    return {
        "opportunity_id": opportunity_id,
        "anchor": {"programme": eff_programme, "title": inferred_anchor},
        "items": items,
    }


# ============================================================================
# Move 2: "Won this before" drawer panel — country-anchored FTS summary
# ============================================================================

@router.get(
    "/intl-coop-summary",
    summary="EU aid history summary for a country (FTS awards)",
    description=(
        "Returns aggregated stats over the EU Financial Transparency System "
        "(FTS) awards for a given country and optional programme: total "
        "count, total amount, average amount, top 5 winners by total amount, "
        "and the 5 most recent awards. Powers the 'Past EU aid in this "
        "country' drawer panel on the Tenderator. Blue tier only."
    ),
)
async def get_intl_coop_summary(
    country: str = Query(..., min_length=2, description="Beneficiary country substring."),
    programme: Optional[str] = Query(None, description="ndici | ipa3 | humanitarian (optional)."),
    years_back: int = Query(5, ge=1, le=20, description="Look back N years from today."),
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    """Country-anchored summary of past EU aid awards. Reads the same FTS
    rows as /api/v2/funding/international-cooperation but aggregates."""
    where = [
        "body_code = 'commission'",
        "item_type = 'funding_recipient'",
        "body_txt ILIKE :bc",
    ]
    params: Dict[str, Any] = {"bc": f"%Beneficiary country: %{country}%"}
    _PROG_FRAG = {
        "ndici": "Neighbourhood, Development and International",
        "ipa3": "Pre-Accession Assistance (IPA III)",
        "humanitarian": "Humanitarian Aid (HUMA)",
    }
    if programme:
        frag = _PROG_FRAG.get(programme.lower())
        if frag:
            where.append("body_txt ILIKE :prog")
            params["prog"] = f"%{frag}%"
    # All three external-action programmes when none specified.
    else:
        where.append(
            "(body_txt ILIKE :p0 OR body_txt ILIKE :p1 OR body_txt ILIKE :p2)"
        )
        params["p0"] = f"%{_PROG_FRAG['ndici']}%"
        params["p1"] = f"%{_PROG_FRAG['ipa3']}%"
        params["p2"] = f"%{_PROG_FRAG['humanitarian']}%"
    # Year cutoff
    cutoff = datetime.utcnow().year - years_back
    where.append("body_txt ~* :yr")
    params["yr"] = rf"Year: ({cutoff}|{'|'.join(str(y) for y in range(cutoff+1, datetime.utcnow().year + 1))})"
    clause = " AND ".join(where)

    rows = db.execute(
        text(
            f"SELECT id, title, body_txt, public_url, document_date "
            f"FROM economy_items WHERE {clause} "
            f"ORDER BY document_date DESC NULLS LAST, id DESC LIMIT 500"
        ),
        params,
    ).fetchall()

    import re as _re

    def _parse(body: str, label: str) -> Optional[str]:
        if not body: return None
        m = _re.search(rf"{_re.escape(label)}:\s*(.+)", body)
        return m.group(1).strip() if m else None

    # Aggregate
    total_amount = 0.0
    winners: Dict[str, Dict[str, Any]] = {}
    recent: List[Dict[str, Any]] = []
    for r in rows:
        b = r.body_txt or ""
        beneficiary = _parse(b, "Beneficiary") or ""
        amount_raw = _parse(b, "EU commitment (total)") or ""
        funding_type = _parse(b, "Funding type") or ""
        dg = _parse(b, "Responsible department") or ""
        subject = _parse(b, "Subject") or ""
        amt = 0.0
        if amount_raw:
            m = _re.search(r"([\d.,]+)", amount_raw.replace("EUR", ""))
            if m:
                try:
                    amt = float(m.group(1).replace(",", ""))
                except ValueError:
                    amt = 0.0
        total_amount += amt
        if beneficiary:
            slot = winners.setdefault(beneficiary, {"count": 0, "amount": 0.0})
            slot["count"] += 1
            slot["amount"] += amt
        if len(recent) < 5:
            recent.append({
                "id": r.id,
                "beneficiary": beneficiary,
                "amount_eur": amt or None,
                "funding_type": funding_type,
                "dg": dg,
                "subject": subject[:160] if subject else None,
                "document_date": r.document_date.isoformat() if r.document_date else None,
                "source_url": r.public_url,
            })

    top_winners = sorted(
        ({"name": k, "count": v["count"], "amount_eur": v["amount"]} for k, v in winners.items()),
        key=lambda x: -x["amount_eur"],
    )[:5]

    count = len(rows)
    return {
        "country": country,
        "programme": programme,
        "years_back": years_back,
        "count": count,
        "total_amount_eur": total_amount or None,
        "avg_amount_eur": (total_amount / count) if count else None,
        "top_winners": top_winners,
        "recent": recent,
    }


# ============================================================================
# Unified F&T feed for the dashboard cockpit
#
# The Tenderator dashboard exposes 4 sources behind a single list view:
# TED tenders + F&T calls for proposals + F&T calls for tenders + F&T
# funded projects. Each source has its own table with its own column
# names. This endpoint normalises them to one shape so the frontend can
# render any source through one component.
# ============================================================================

@router.get(
    "/unified-feed",
    summary="Mixed-source opportunity feed for the dashboard",
    description=(
        "Returns a paginated list of opportunities from one of 8 sources: "
        "**ted** (member-state TED notices), **ft_proposals** (F&T calls "
        "for proposals), **ft_tenders** (F&T calls for tenders), "
        "**ft_projects** (F&T funded projects), **agency** (decentralised "
        "EU agency procurement in economy_items), **intl_coop** (EU FTS "
        "awards — NDICI / IPA III / Humanitarian Aid), **matches** (the "
        "user's scored matches across all sources), or **all** "
        "(interleaved). Lenses: `personalised` (default true), "
        "`external_action`, `framework_only`, `client_filter`. "
        "Normalises every source to a common shape: {id, source, "
        "external_id, title, description, status, deadline, budget, "
        "currency, source_url, organisation, country, programme, "
        "published_at, detected_lang, translated_from?}. Blue tier only."
    ),
)
async def get_unified_feed(
    source: str = Query("all", description="ted | ft_proposals | ft_tenders | ft_projects | agency | matches | all"),
    match_source: str = Query("all", description="When source=matches: all | ted | ft_proposals | ft_tenders | agency. Backed by tender_matches (TED) + on-the-fly scoring (F&T + agency) against the user's TenderProfile keywords + CPV + countries, blended with their MEUB Policy Interests when personalised is on."),
    q: Optional[str] = Query(None, description="Substring match on title + description"),
    programme: Optional[str] = Query(None, description="EU funding programme code (e.g. EU4H, HE, CEF) — filters F&T calls/projects by topic_id prefix"),
    body: Optional[str] = Query(None, description="When source=agency: economy_items.body_code (e.g. efsa, ema, efca) — filters to one decentralised agency."),
    framework_only: bool = Query(False, description="When true (Move 5 lens), narrow source=agency to item_type='framework' — only EU-institution Framework Contracts (Commission/EIB/EP/EEAS/Council/ECB FWCs). No effect on other sources."),
    status_filter: Optional[str] = Query(None, alias="status", description="open | forthcoming | closed"),
    lang: Optional[str] = Query(None, description="Render titles + descriptions in this Brubru language (en/es/ca/fr/it/nl). Items whose detected_lang is outside the 6 get served from <table>_translations when available; English-source items pass through."),
    client_filter: bool = Query(False, description="Apply the user's private_guide pursuits filter (CA / programme / country / keywords). Requires private_guide_slug + meta_json on the user."),
    personalised: bool = Query(True, description="When true (default), narrow every source by the user's MEUB Policy Interests (keywords from policy_taxonomy + CPV prefixes for TED). Set false to see the unfiltered feed. No-op when the user has no interests set."),
    external_action: bool = Query(False, description="When true, narrow every source to EU external-action contracts: TED notices from DG INTPA / NEAR / ECHO / FPI / EEAS or CPV 71/73/79/80; F&T calls/projects under NDICI / IPA / Humanitarian / Global Europe programmes. Combines with personalised + pursuits via AND. Off by default."),
    beneficiary_country: Optional[str] = Query(None, description="External-action only: substring match on title + description / objective to narrow to opportunities implementing in a given country (e.g. 'Ukraine', 'Morocco', 'Türkiye'). Independent of external_action; can be used alone."),
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    from models.funding_tenders import (
        FtCallForProposals,
        FtCallForTenders,
        FtFundedProject,
    )
    from sqlalchemy import or_, text as _sql_text

    # === Layer 2: per-client pursuits pre-filter ===
    # When client_filter=true and the user has a private_guide_slug with
    # meta_json.pursuits_filter, we narrow every source by keyword / CA /
    # country / programme to the client's eligible scope. Fail-soft: if no
    # filter is configured, the call behaves as if client_filter=false.
    pursuits = None
    if client_filter and getattr(current_user, "private_guide_slug", None):
        try:
            row = db.execute(
                _sql_text(
                    "SELECT meta_json FROM private_guides "
                    "WHERE slug=:slug AND filename='_meta.json' AND meta_json IS NOT NULL LIMIT 1"
                ),
                {"slug": current_user.private_guide_slug},
            ).fetchone()
            if row and row[0]:
                meta = row[0]
                pursuits = meta.get("pursuits_filter") if isinstance(meta, dict) else None
        except Exception as exc:
            logger.warning("[client-filter] meta_json lookup failed for slug=%s: %s",
                           current_user.private_guide_slug, exc)
            pursuits = None

    def _apply_pursuits_filter_ted(qry):
        if not pursuits: return qry
        kws = pursuits.get("keywords") or []
        cas = pursuits.get("contracting_authorities") or []
        cs = pursuits.get("countries") or []
        ored = []
        for kw in kws:
            ored.append(Tender.title.ilike(f"%{kw}%"))
            ored.append(Tender.description.ilike(f"%{kw}%"))
        for ca in cas:
            ored.append(Tender.official_name.ilike(f"%{ca}%"))
        for c in cs:
            ored.append(Tender.buyer_country == c)
        return qry.filter(or_(*ored)) if ored else qry

    def _apply_pursuits_filter_proposals(qry):
        if not pursuits: return qry
        kws = pursuits.get("keywords") or []
        progs = pursuits.get("programmes") or []
        ored = []
        for kw in kws:
            ored.append(FtCallForProposals.title.ilike(f"%{kw}%"))
            ored.append(FtCallForProposals.description.ilike(f"%{kw}%"))
        for p in progs:
            ored.append(FtCallForProposals.framework_programme.ilike(f"%{p}%"))
        return qry.filter(or_(*ored)) if ored else qry

    def _apply_pursuits_filter_tenders(qry):
        if not pursuits: return qry
        kws = pursuits.get("keywords") or []
        cas = pursuits.get("contracting_authorities") or []
        ored = []
        for kw in kws:
            ored.append(FtCallForTenders.title.ilike(f"%{kw}%"))
            ored.append(FtCallForTenders.description.ilike(f"%{kw}%"))
        for ca in cas:
            ored.append(FtCallForTenders.contracting_authority.ilike(f"%{ca}%"))
        return qry.filter(or_(*ored)) if ored else qry

    def _apply_pursuits_filter_projects(qry):
        if not pursuits: return qry
        kws = pursuits.get("keywords") or []
        progs = pursuits.get("programmes") or []
        cs = pursuits.get("countries") or []
        ored = []
        for kw in kws:
            ored.append(FtFundedProject.title.ilike(f"%{kw}%"))
            ored.append(FtFundedProject.objective.ilike(f"%{kw}%"))
        for p in progs:
            ored.append(FtFundedProject.framework_programme.ilike(f"%{p}%"))
        for c in cs:
            ored.append(FtFundedProject.coordinator_country == c)
        return qry.filter(or_(*ored)) if ored else qry

    # === Layer 1: MEUB Policy-Interest pre-filter ===
    # When personalised=true (default) and the user has policy_interests set, narrow
    # every source by the user's interest keywords + CPV prefixes (TED only).
    # If interests is empty, the filter is a no-op and personalised_applied=false
    # in the response — frontend can then prompt the user to set interests.
    interests = _interest_list(current_user) if personalised else []
    pi_keywords = sorted(keywords_for_interests(interests)) if interests else []
    pi_cpv_prefixes = sorted(cpv_for_interests(interests)) if interests else []
    personalised_applied = bool(pi_keywords or pi_cpv_prefixes)

    def _apply_pi_filter_ted(qry):
        if not personalised_applied:
            return qry
        ored = []
        for kw in pi_keywords:
            ored.append(Tender.title.ilike(f"%{kw}%"))
            ored.append(Tender.description.ilike(f"%{kw}%"))
        for pref in pi_cpv_prefixes:
            ored.append(Tender.cpv_main.ilike(f"{pref}%"))
        return qry.filter(or_(*ored)) if ored else qry

    def _apply_pi_filter_proposals(qry):
        if not personalised_applied or not pi_keywords:
            return qry
        ored = [FtCallForProposals.title.ilike(f"%{kw}%") for kw in pi_keywords]
        ored += [FtCallForProposals.description.ilike(f"%{kw}%") for kw in pi_keywords]
        return qry.filter(or_(*ored))

    def _apply_pi_filter_tenders(qry):
        if not personalised_applied or not pi_keywords:
            return qry
        ored = [FtCallForTenders.title.ilike(f"%{kw}%") for kw in pi_keywords]
        ored += [FtCallForTenders.description.ilike(f"%{kw}%") for kw in pi_keywords]
        return qry.filter(or_(*ored))

    def _apply_pi_filter_projects(qry):
        if not personalised_applied or not pi_keywords:
            return qry
        ored = [FtFundedProject.title.ilike(f"%{kw}%") for kw in pi_keywords]
        ored += [FtFundedProject.objective.ilike(f"%{kw}%") for kw in pi_keywords]
        return qry.filter(or_(*ored))

    # === External-action lens (Move 1, 15 Jun 2026) ===
    # Narrows TED + F&T to EU external-action contracts: notices from DG INTPA /
    # NEAR / ECHO / FPI / EEAS or CPV 71/73/79/80 (architectural-engineering /
    # research / business-management consultancy / education-training divisions
    # that dominate development-cooperation services); F&T programmes containing
    # NDICI / IPA / HUMA / Global Europe / Erasmus Mundus. The beneficiary_country
    # facet is a free-text substring over title + description / objective.
    _EXT_DG_PATTERNS = (
        "INTPA", "NEAR", "ECHO", "FPI", "EEAS",
        "International Partnerships", "Neighbourhood",
        "Humanitarian", "DEVCO", "External Action",
        "Commission européenne", "European Commission",
    )
    # Exact framework_programme matches (no substring — 'IPA' / 'HUMA' / 'ECHO'
    # as substrings catch unrelated titles like "OCCUPATIONAL" or "HUMAN-CENTRED
    # AI". Today only NDICI is populated in ft_funded_projects; the other codes
    # are listed so the filter widens automatically when those programmes ingest.)
    _EXT_FT_PROGRAMMES = (
        "NDICI", "IPA III", "IPA II", "IPA",
        "HUMA", "Humanitarian Aid",
        "Global Europe", "NDICI - Global Europe",
        "Erasmus Mundus", "ERASMUS-MUNDUS",
    )

    def _apply_external_filter_ted(qry):
        """TED narrowing for the external-action lens: ONLY buyer-name match
        on DG INTPA / NEAR / ECHO / FPI / EEAS or the umbrella 'European
        Commission' / 'Commission européenne'. CPV alone proved too noisy
        (catches Dutch municipalities under CPV 80 training). Today our TED
        ingest holds member-state notices only, so the strict filter returns
        zero rows; the moment EU-institution TED notices are ingested it
        will start populating without code changes."""
        if not external_action:
            return qry
        ored = [Tender.official_name.ilike(f"%{pat}%") for pat in _EXT_DG_PATTERNS]
        return qry.filter(or_(*ored)) if ored else qry

    def _apply_external_filter_proposals(qry):
        if not external_action:
            return qry
        # framework_programme is structured; exact match avoids substring false-pos.
        return qry.filter(FtCallForProposals.framework_programme.in_(_EXT_FT_PROGRAMMES))

    def _apply_external_filter_tenders(qry):
        if not external_action:
            return qry
        # ft_calls_for_tenders has no framework_programme column; we fall back
        # to title-substring on the full programme names (no abbreviations).
        full_names = ("NDICI", "Global Europe", "Pre-Accession Assistance",
                      "Humanitarian Aid", "Erasmus Mundus")
        ored = [FtCallForTenders.title.ilike(f"%{n}%") for n in full_names]
        ored += [FtCallForTenders.description.ilike(f"%{n}%") for n in full_names]
        return qry.filter(or_(*ored))

    def _apply_external_filter_projects(qry):
        if not external_action:
            return qry
        return qry.filter(FtFundedProject.framework_programme.in_(_EXT_FT_PROGRAMMES))

    # Beneficiary country: free-text substring over title + description/objective.
    def _apply_country_filter_ted(qry):
        if not beneficiary_country:
            return qry
        c = f"%{beneficiary_country}%"
        return qry.filter(or_(
            Tender.title.ilike(c),
            Tender.description.ilike(c),
            Tender.buyer_country.ilike(beneficiary_country),
        ))

    def _apply_country_filter_proposals(qry):
        if not beneficiary_country:
            return qry
        c = f"%{beneficiary_country}%"
        return qry.filter(or_(
            FtCallForProposals.title.ilike(c),
            FtCallForProposals.description.ilike(c),
        ))

    def _apply_country_filter_tenders(qry):
        if not beneficiary_country:
            return qry
        c = f"%{beneficiary_country}%"
        return qry.filter(or_(
            FtCallForTenders.title.ilike(c),
            FtCallForTenders.description.ilike(c),
        ))

    def _apply_country_filter_projects(qry):
        if not beneficiary_country:
            return qry
        c = f"%{beneficiary_country}%"
        return qry.filter(or_(
            FtFundedProject.title.ilike(c),
            FtFundedProject.objective.ilike(c),
            FtFundedProject.coordinator_country.ilike(beneficiary_country),
        ))

    valid_sources = {"all", "matches", "ted", "ft_proposals", "ft_tenders", "ft_projects", "agency", "intl_coop"}
    if source not in valid_sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"source must be one of {sorted(valid_sources)}",
        )

    offset = (page - 1) * limit
    items: List[dict] = []
    totals = {"ted": 0, "ft_proposals": 0, "ft_tenders": 0, "ft_projects": 0, "agency": 0, "intl_coop": 0}
    now = datetime.utcnow()

    # Translation overlay (MEUB-news pattern, migration 133).
    # Brubru's 6 are en/es/ca/fr/it/nl. Items whose detected_lang is outside
    # the 6 (PL/DE/CS/PT/BG/SV/FI/…) get their title+summary served from the
    # per-source <table>_translations sidecar when a row exists for the
    # requested lang. Items already in one of the 6 pass through. The
    # `lang` query param is the target; we default to 'en' if unset.
    _SIX_LANGS = {"en", "es", "ca", "fr", "it", "nl"}
    target_lang = (lang or "en").lower()
    if target_lang not in _SIX_LANGS:
        target_lang = "en"

    # Translation maps keyed by source-tag → {row_id (as str): (title, summary)}.
    _tmaps: Dict[str, Dict[str, Tuple[Optional[str], Optional[str]]]] = {
        "ted": {}, "ft_proposals": {}, "ft_tenders": {},
        "ft_projects": {}, "agency": {},
    }

    def _fetch_translations(src_tag: str, table: str, fk: str, ids: List[Any]) -> None:
        """Populate _tmaps[src_tag] for the given row ids in target_lang.

        Empty ids = no-op. Both INTEGER and UUID PK columns are supported —
        we cast the FK to text on BOTH sides so the comparison is uniform.
        """
        if not ids:
            return
        try:
            rows = db.execute(
                _sql_text(
                    f"SELECT {fk}::text AS rid, title, summary "
                    f"FROM {table} WHERE lang = :lang AND {fk}::text = ANY(:ids)"
                ),
                {"lang": target_lang, "ids": [str(i) for i in ids]},
            ).fetchall()
            for r in rows:
                _tmaps[src_tag][r.rid] = (r.title, r.summary)
        except Exception as exc:
            logger.warning("translation overlay (%s) failed: %s", src_tag, exc)
            db.rollback()

    def _apply_translation(item: Dict[str, Any]) -> Dict[str, Any]:
        """If a translated row exists for this item, swap title + description
        and surface the detected_lang as translated_from. Otherwise pass-through."""
        src = item.get("source")
        if not src or src not in _tmaps:
            return item
        # Item id format is "<source>:<row_id>" — recover the row part.
        raw_id = item.get("id", "")
        rid = raw_id.split(":", 1)[-1] if ":" in raw_id else raw_id
        cached = _tmaps[src].get(rid)
        detected = item.get("detected_lang")
        if cached and cached[0] and detected and detected != target_lang:
            t_title, t_sum = cached
            item["title"] = t_title or item["title"]
            if t_sum:
                item["description"] = t_sum[:600]
            item["translated_from"] = detected
        return item

    # Per-source sidecar metadata: (table, fk-column).
    _TRANSLATION_TABLES = {
        "ted":          ("tenders_translations",                  "tender_id"),
        "ft_proposals": ("ft_calls_for_proposals_translations",   "call_id"),
        "ft_tenders":   ("ft_calls_for_tenders_translations",     "tender_uuid"),
        "ft_projects":  ("ft_funded_projects_translations",       "project_uuid"),
        "agency":       ("economy_items_translations",            "item_id"),
    }

    def _overlay_translations(item_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """For every item whose detected_lang is foreign (outside the 6) AND
        != target_lang, batched-look-up the sidecar translation and swap in
        title + description. Single pass per source. No-op on EN target +
        EN-source items."""
        if not item_list:
            return item_list
        # Bucket the foreign-language items by source.
        foreign_by_src: Dict[str, List[str]] = {k: [] for k in _TRANSLATION_TABLES}
        for it in item_list:
            src = it.get("source")
            if src not in foreign_by_src:
                continue
            d = it.get("detected_lang")
            if not d or d == target_lang:
                continue
            if d in _SIX_LANGS:
                # Already in a Brubru lang. If it's not the target lang, we
                # still want to translate it (e.g. Italian title shown in
                # Spanish), so don't skip.
                pass
            raw_id = it.get("id", "")
            rid = raw_id.split(":", 1)[-1] if ":" in raw_id else raw_id
            if rid:
                foreign_by_src[src].append(rid)
        for src, ids in foreign_by_src.items():
            if not ids:
                continue
            table, fk = _TRANSLATION_TABLES[src]
            _fetch_translations(src, table, fk, ids)
        return [_apply_translation(it) for it in item_list]

    # economy_items funding item_types — populated by services/scrapers/agency_procurement.py
    # via the register_resource pattern in api/v2/funding/agency_procurement.py.
    _AGENCY_ITEM_TYPES = ("tender", "grant", "eoi_call", "startup_funding", "framework")
    # Map body_code → display acronym for the organisation slot. Anything not
    # listed falls back to body_code.upper(); add new entries when new agency
    # folders are registered.
    _AGENCY_LABELS = {
        "efca": "EFCA", "cedefop": "Cedefop", "ema": "EMA", "efsa": "EFSA",
        "eurojust": "Eurojust", "etf": "ETF", "eige": "EIGE", "euaa": "EUAA",
        "fra": "FRA", "era": "ERA", "eurofound": "Eurofound", "eea": "EEA",
        "echa": "ECHA", "euda": "EUDA", "ecdc": "ECDC", "eu_osha": "EU-OSHA",
        "enisa": "ENISA", "commission": "European Commission",
        "innovfund": "Innovation Fund", "just": "Justice Programme",
        "eib": "EIB",
        "eeas": "EEAS", "parliament": "European Parliament",
        "council": "Council of the EU", "ecb": "ECB",
    }

    # Map an EU funding programme code to the topic_id / call_id prefixes used on
    # the F&T portal. The programme is NOT in framework_programme (that holds the
    # period, e.g. "2021 - 2027"); it lives in the topic_id prefix.
    PROGRAMME_TOPIC_PREFIXES = {
        "HE": ["HORIZON"], "H2020": ["H2020"], "FP7": ["FP7"],
        "EU4H": ["EU4"], "DEP": ["DIGITAL"], "CEF": ["CEF"], "LIFE": ["LIFE"],
        "ERASMUS": ["ERASMUS"], "EIC": ["EIC", "HORIZON-EIC"], "CREA": ["CREA"],
        "AMIF": ["AMIF"], "BMVI": ["BMVI"], "ISF": ["ISF"], "JTM": ["JTM"],
    }
    prog_prefixes = (
        PROGRAMME_TOPIC_PREFIXES.get(programme.upper(), [programme.upper()])
        if programme else None
    )

    def _proposal_programme_clause():
        # OR of topic_id/call_id ILIKE '<prefix>%' across the programme's prefixes.
        clauses = []
        for pref in prog_prefixes:
            clauses.append(FtCallForProposals.topic_id.ilike(f"{pref}%"))
            clauses.append(FtCallForProposals.call_id.ilike(f"{pref}%"))
        return or_(*clauses)

    def _ted_query():
        qry = db.query(Tender)
        if status_filter == "open":
            qry = qry.filter((Tender.submission_deadline > now) | (Tender.submission_deadline.is_(None)))
        elif status_filter == "closed":
            qry = qry.filter(Tender.submission_deadline < now)
        else:
            # Default: hide opportunities whose submission deadline has passed.
            qry = qry.filter((Tender.submission_deadline >= now) | (Tender.submission_deadline.is_(None)))
        if q:
            qry = qry.filter(Tender.title.ilike(f"%{q}%"))
        qry = _apply_pursuits_filter_ted(qry)
        qry = _apply_pi_filter_ted(qry)
        qry = _apply_external_filter_ted(qry)
        qry = _apply_country_filter_ted(qry)
        return qry

    def _proposals_query():
        qry = db.query(FtCallForProposals).filter(FtCallForProposals.is_test == False)  # noqa: E712
        if status_filter == "closed":
            qry = qry.filter(FtCallForProposals.deadline < now)
        elif status_filter:
            qry = qry.filter(FtCallForProposals.status == status_filter.lower())
            qry = qry.filter((FtCallForProposals.deadline >= now) | (FtCallForProposals.deadline.is_(None)))
        else:
            # Default: hide calls whose deadline has passed.
            qry = qry.filter((FtCallForProposals.deadline >= now) | (FtCallForProposals.deadline.is_(None)))
        if prog_prefixes:
            qry = qry.filter(_proposal_programme_clause())
        if q:
            qry = qry.filter(FtCallForProposals.title.ilike(f"%{q}%"))
        qry = _apply_pursuits_filter_proposals(qry)
        qry = _apply_pi_filter_proposals(qry)
        qry = _apply_external_filter_proposals(qry)
        qry = _apply_country_filter_proposals(qry)
        return qry

    def _tenders_query():
        qry = db.query(FtCallForTenders).filter(FtCallForTenders.is_test == False)  # noqa: E712
        if status_filter == "closed":
            qry = qry.filter(FtCallForTenders.deadline < now)
        elif status_filter:
            qry = qry.filter(FtCallForTenders.status == status_filter.lower())
            qry = qry.filter((FtCallForTenders.deadline >= now) | (FtCallForTenders.deadline.is_(None)))
        else:
            # Default: hide calls whose deadline has passed.
            qry = qry.filter((FtCallForTenders.deadline >= now) | (FtCallForTenders.deadline.is_(None)))
        if q:
            qry = qry.filter(FtCallForTenders.title.ilike(f"%{q}%"))
        qry = _apply_pursuits_filter_tenders(qry)
        qry = _apply_pi_filter_tenders(qry)
        qry = _apply_external_filter_tenders(qry)
        qry = _apply_country_filter_tenders(qry)
        return qry

    def _projects_query():
        qry = db.query(FtFundedProject).filter(FtFundedProject.is_test == False)  # noqa: E712
        if q:
            qry = qry.filter(FtFundedProject.title.ilike(f"%{q}%"))
        qry = _apply_pursuits_filter_projects(qry)
        qry = _apply_pi_filter_projects(qry)
        qry = _apply_external_filter_projects(qry)
        qry = _apply_country_filter_projects(qry)
        return qry

    # --- Agency (decentralised EU bodies' own procurement) -------------------
    # Reads economy_items, the same store the public /api/v2/funding/{agency}-*
    # endpoints serve. body_code = agency slug, item_type ∈ tender|grant|
    # eoi_call|startup_funding. document_date is the deadline. New agencies
    # appear here automatically as soon as a scraper backfills their rows.
    def _agency_where_params(extra_body: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        # Move 5 (15 Jun 2026): framework_only narrows agency view to FWCs.
        if framework_only:
            where = ["item_type = 'framework'"]
            params: Dict[str, Any] = {}
        else:
            where = ["item_type = ANY(:agency_types)"]
            params: Dict[str, Any] = {"agency_types": list(_AGENCY_ITEM_TYPES)}
        if status_filter == "closed":
            where.append("document_date < :now")
            params["now"] = now
        elif status_filter == "open":
            where.append("(document_date > :now OR document_date IS NULL)")
            params["now"] = now
        else:
            where.append("(document_date >= :now OR document_date IS NULL)")
            params["now"] = now
        if q:
            where.append("(title ILIKE :q OR summary ILIKE :q)")
            params["q"] = f"%{q}%"
        # `body` is the query-param scope (one agency); `extra_body` is a
        # closure-call override (unused so far but kept for future use).
        scoped_body = extra_body or body
        if scoped_body:
            where.append("body_code = :body")
            params["body"] = scoped_body
        if pursuits:
            kws = pursuits.get("keywords") or []
            if kws:
                kw_ors = []
                for i, kw in enumerate(kws):
                    pn = f"kw_{i}"
                    kw_ors.append(f"(title ILIKE :{pn} OR summary ILIKE :{pn})")
                    params[pn] = f"%{kw}%"
                where.append("(" + " OR ".join(kw_ors) + ")")
        if personalised_applied and pi_keywords:
            kw_ors = []
            for i, kw in enumerate(pi_keywords):
                pn = f"pikw_{i}"
                kw_ors.append(f"(title ILIKE :{pn} OR summary ILIKE :{pn})")
                params[pn] = f"%{kw}%"
            where.append("(" + " OR ".join(kw_ors) + ")")
        if beneficiary_country:
            where.append("(title ILIKE :bcountry OR summary ILIKE :bcountry)")
            params["bcountry"] = f"%{beneficiary_country}%"
        return " AND ".join(where), params

    def _agency_count() -> int:
        clause, params = _agency_where_params()
        try:
            return db.execute(
                _sql_text(f"SELECT count(*) FROM economy_items WHERE {clause}"),
                params,
            ).scalar() or 0
        except Exception as exc:
            logger.warning("agency count failed: %s", exc)
            db.rollback()
            return 0

    def _agency_rows(page_offset: int, page_limit: int):
        clause, params = _agency_where_params()
        params["limit"] = page_limit
        params["offset"] = page_offset
        try:
            return db.execute(
                _sql_text(
                    f"SELECT id, body_code, item_type, title, summary, public_url, "
                    f"       document_date, creation_date, detected_lang "
                    f"FROM economy_items WHERE {clause} "
                    f"ORDER BY document_date ASC NULLS LAST, id DESC "
                    f"LIMIT :limit OFFSET :offset"
                ),
                params,
            ).fetchall()
        except Exception as exc:
            logger.warning("agency rows failed: %s", exc)
            db.rollback()
            return []

    # --- intl_coop (EU external-action FTS awards) ---------------------------
    # Reads economy_items(body_code='commission', item_type='funding_recipient')
    # — same store the public /api/v2/funding/international-cooperation
    # endpoint serves. Surfaces the AWARDS side of NDICI / IPA III / Humanitarian
    # Aid so a Tenderator user can see WHO won EU aid money WHERE under WHICH
    # instrument, alongside the bids feed.
    def _intl_coop_where_params() -> Tuple[str, Dict[str, Any]]:
        where = [
            "body_code = 'commission'",
            "item_type = 'funding_recipient'",
        ]
        params: Dict[str, Any] = {}
        # Only one of the three external-action programmes per row; we always
        # include rows whose body_txt mentions any of them.
        prog_clauses = []
        for i, frag in enumerate((
            "Neighbourhood, Development and International",
            "Pre-Accession Assistance (IPA III)",
            "Humanitarian Aid (HUMA)",
        )):
            prog_clauses.append(f"body_txt ILIKE :prog{i}")
            params[f"prog{i}"] = f"%{frag}%"
        where.append("(" + " OR ".join(prog_clauses) + ")")
        if q:
            where.append("(title ILIKE :q OR body_txt ILIKE :q)")
            params["q"] = f"%{q}%"
        if beneficiary_country:
            where.append("body_txt ILIKE :bcountry_ic")
            params["bcountry_ic"] = f"%Beneficiary country: %{beneficiary_country}%"
        if personalised_applied and pi_keywords:
            kw_ors = []
            for i, kw in enumerate(pi_keywords):
                pn = f"pikw_ic_{i}"
                kw_ors.append(f"(title ILIKE :{pn} OR body_txt ILIKE :{pn})")
                params[pn] = f"%{kw}%"
            where.append("(" + " OR ".join(kw_ors) + ")")
        return " AND ".join(where), params

    def _intl_coop_count() -> int:
        clause, params = _intl_coop_where_params()
        try:
            return db.execute(
                _sql_text(f"SELECT count(*) FROM economy_items WHERE {clause}"),
                params,
            ).scalar() or 0
        except Exception as exc:
            logger.warning("intl_coop count failed: %s", exc)
            db.rollback()
            return 0

    def _intl_coop_rows(page_offset: int, page_limit: int):
        clause, params = _intl_coop_where_params()
        params["limit"] = page_limit
        params["offset"] = page_offset
        try:
            return db.execute(
                _sql_text(
                    f"SELECT id, title, body_txt, public_url, document_date, creation_date "
                    f"FROM economy_items WHERE {clause} "
                    f"ORDER BY document_date DESC NULLS LAST, id DESC "
                    f"LIMIT :limit OFFSET :offset"
                ),
                params,
            ).fetchall()
        except Exception as exc:
            logger.warning("intl_coop rows failed: %s", exc)
            db.rollback()
            return []

    def _serialise_ted(t):
        return {
            "id": f"ted:{t.id}",
            "source": "ted",
            "external_id": t.publication_number,
            "title": t.title,
            "description": (t.description or "")[:600] if t.description else None,
            "status": t.status,
            "deadline": t.submission_deadline.isoformat() if t.submission_deadline else None,
            "budget": float(t.estimated_value) if t.estimated_value else None,
            "currency": getattr(t, "estimated_value_currency", None) or "EUR",
            "source_url": getattr(t, "ted_url", None) or "",
            "organisation": getattr(t, "official_name", None),
            "country": t.buyer_country,
            "programme": None,
            "published_at": t.publication_date.isoformat() if t.publication_date else None,
            "detected_lang": getattr(t, "detected_lang", None),
        }

    def _serialise_proposal(p):
        return {
            "id": f"ft_proposals:{p.id}",
            "source": "ft_proposals",
            "external_id": p.topic_id,
            "title": p.title,
            "description": (p.description or "")[:600] if p.description else None,
            "status": p.status,
            "deadline": p.deadline.isoformat() if p.deadline else None,
            "budget": float(p.indicative_budget) if p.indicative_budget else None,
            "currency": p.budget_currency or "EUR",
            "source_url": p.source_url,
            "organisation": None,
            "country": None,
            "programme": p.framework_programme,
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "detected_lang": getattr(p, "detected_lang", None),
        }

    def _serialise_tender_ft(t):
        return {
            "id": f"ft_tenders:{t.id}",
            "source": "ft_tenders",
            "external_id": t.tender_reference,
            "title": t.title,
            "description": (t.description or "")[:600] if t.description else None,
            "status": t.status,
            "deadline": t.deadline.isoformat() if t.deadline else None,
            "budget": float(t.estimated_value) if t.estimated_value else None,
            "currency": t.value_currency or "EUR",
            "source_url": t.source_url,
            "organisation": t.contracting_authority,
            "country": None,
            "programme": None,
            "published_at": t.published_at.isoformat() if t.published_at else None,
            "detected_lang": getattr(t, "detected_lang", None),
        }

    def _clean_coordinator(raw: Optional[str]) -> Optional[str]:
        """ft_funded_projects.coordinator_name sometimes carries the raw
        F&T Portal JSON ([{role,pic,legalName,postalAddress,...}, ...]) — about
        26% of rows on 15 Jun 2026. Extract `legalName` of the coordinator
        if present; otherwise return the value as-is unless it starts with
        '[{' / '{' (in which case strip braces to avoid dumping JSON in cards)."""
        if not raw:
            return None
        s = raw.strip()
        if not (s.startswith("[{") or s.startswith("{")):
            return raw
        try:
            import json as _json
            obj = _json.loads(s)
            if isinstance(obj, list):
                coords = [x for x in obj if isinstance(x, dict) and x.get("role") == "coordinator"]
                pool = coords if coords else [x for x in obj if isinstance(x, dict)]
                if pool:
                    name = pool[0].get("legalName") or pool[0].get("shortName")
                    if name:
                        return name
            elif isinstance(obj, dict):
                name = obj.get("legalName") or obj.get("shortName")
                if name:
                    return name
        except (ValueError, TypeError):
            pass
        return None  # fall back to nothing rather than raw JSON

    def _serialise_project(p):
        return {
            "id": f"ft_projects:{p.id}",
            "source": "ft_projects",
            "external_id": p.project_id,
            "title": p.title,
            "description": (p.objective or "")[:600] if p.objective else None,
            "status": p.status,
            "deadline": p.end_date.isoformat() if p.end_date else None,
            "budget": float(p.eu_contribution) if p.eu_contribution else (float(p.total_cost) if p.total_cost else None),
            "currency": p.cost_currency or "EUR",
            "source_url": p.source_url,
            "organisation": _clean_coordinator(p.coordinator_name),
            "country": p.coordinator_country,
            "programme": p.framework_programme,
            "published_at": p.start_date.isoformat() if p.start_date else None,
            "detected_lang": getattr(p, "detected_lang", None),
        }

    def _parse_fts_field(body: str, label: str) -> Optional[str]:
        """Extract a 'Label: value' line from the FTS body_txt."""
        if not body: return None
        import re as _re
        m = _re.search(rf"{_re.escape(label)}:\s*(.+)", body)
        return m.group(1).strip() if m else None

    def _serialise_intl_coop(r):
        """FTS award row → unified shape. The body_txt holds structured
        'Label: value' lines (Beneficiary, EU commitment (total), Funding type,
        Programme, Responsible department, Beneficiary country, Subject, Year).
        We parse them inline so the card has all the fields the user needs to
        spot competitive intel at a glance."""
        body = r.body_txt or ""
        beneficiary = _parse_fts_field(body, "Beneficiary") or r.title
        country = _parse_fts_field(body, "Beneficiary country")
        programme = _parse_fts_field(body, "Programme")
        funding_type = _parse_fts_field(body, "Funding type")
        dg = _parse_fts_field(body, "Responsible department")
        subject = _parse_fts_field(body, "Subject")
        amount_raw = _parse_fts_field(body, "EU commitment (total)") or ""
        budget = None
        if amount_raw:
            import re as _re
            m = _re.search(r"([\d.,]+)", amount_raw.replace("EUR", ""))
            if m:
                try:
                    budget = float(m.group(1).replace(",", ""))
                except ValueError:
                    budget = None
        # Short FT-programme tag for the chip slot.
        prog_short = ""
        if programme:
            pl = programme.lower()
            if "neighbourhood, development" in pl: prog_short = "NDICI"
            elif "pre-accession" in pl: prog_short = "IPA III"
            elif "humanitarian" in pl: prog_short = "Humanitarian Aid"
        # The subject often carries the contract slug; pick the best title.
        title = subject or beneficiary or r.title or "EU award"
        return {
            "id": f"intl_coop:{r.id}",
            "source": "intl_coop",
            "external_id": _parse_fts_field(body, "Legal commitment ref"),
            "title": title[:200],
            "description": (
                f"Beneficiary: {beneficiary} | Funding type: {funding_type or 'Unknown'}"
                if beneficiary else None
            ),
            "status": None,
            "deadline": None,
            "budget": budget,
            "currency": "EUR",
            "source_url": r.public_url,
            "organisation": beneficiary,
            "country": country,
            "programme": prog_short or (programme[:40] if programme else None),
            "published_at": r.document_date.isoformat() if r.document_date else None,
            "detected_lang": None,
            "funding_type": funding_type,
            "dg": dg,
        }

    def _serialise_agency(r):
        # economy_items row → unified shape. body_code is the agency slug; we
        # show its display acronym in the organisation slot and re-purpose the
        # programme slot for a short ITEM-TYPE hint (Tender / Grant / EOI /
        # Startup funding) so the user immediately sees what kind of item it
        # is regardless of which agency runs it.
        type_label = {
            "tender": "Tender",
            "grant": "Grant",
            "eoi_call": "Call for EOI",
            "startup_funding": "Startup funding",
            "framework": "Framework contract",
        }.get(r.item_type, r.item_type)
        organisation = _AGENCY_LABELS.get(r.body_code, r.body_code.upper())
        return {
            "id": f"agency:{r.id}",
            "source": "agency",
            "external_id": r.body_code,
            "title": r.title,
            "description": (r.summary or "")[:600] if r.summary else None,
            "status": None,
            "deadline": r.document_date.isoformat() if r.document_date else None,
            "budget": None,
            "currency": "EUR",
            "source_url": r.public_url,
            "organisation": organisation,
            "country": None,
            "programme": type_label,
            "published_at": r.creation_date.isoformat() if r.creation_date else None,
            "detected_lang": getattr(r, "detected_lang", None),
        }

    try:
        # NEW: "matches" source. Returns three sub-feeds, each scored:
        #   - TED:           pulled from tender_matches (persisted score)
        #   - F&T proposals: on-the-fly score (keyword + country overlap)
        #   - F&T tenders:   on-the-fly score (CPV + keyword + country overlap)
        # `match_source` narrows to one (ted, ft_proposals, ft_tenders) or
        # "all" (the default) which interleaves all three.
        if source == "matches":
            try:
                from models.tender import TenderProfile
                from models.funding_tenders import FtCallForProposals, FtCallForTenders

                profile = (
                    db.query(TenderProfile)
                    .filter(TenderProfile.user_id == current_user.id)
                    .first()
                )
                kw_lower = [k.lower() for k in (profile.keywords or [])] if profile else []
                cpv_two = set((c[:2] for c in (profile.cpv_categories or []) if c)) if profile else set()
                countries = set(profile.countries_of_interest or []) if profile else set()
                # Blend in the user's MEUB Policy Interests so matches work even
                # without a saved TenderProfile (or to enrich a thin one).
                if personalised_applied:
                    kw_lower = sorted(set(kw_lower) | set(pi_keywords))
                    cpv_two = cpv_two | set(pi_cpv_prefixes)

                total_ted_matches = 0
                total_proposal_matches = 0
                total_tender_matches = 0
                total_agency_matches = 0

                bucket_ted: List[Dict[str, Any]] = []
                bucket_proposals: List[Dict[str, Any]] = []
                bucket_tenders: List[Dict[str, Any]] = []
                bucket_agency: List[Dict[str, Any]] = []

                # --- TED via persisted tender_matches ---
                if match_source in ("all", "ted"):
                    qry_ted = (
                        db.query(TenderMatch, Tender)
                        .join(Tender, Tender.id == TenderMatch.tender_id)
                        .filter(TenderMatch.user_id == current_user.id)
                        .filter(TenderMatch.is_dismissed == False)  # noqa: E712
                        .filter(or_(Tender.submission_deadline >= now, Tender.submission_deadline.is_(None)))
                    )
                    if q:
                        qry_ted = qry_ted.filter(Tender.title.ilike(f"%{q}%"))
                    total_ted_matches = qry_ted.count()
                    if match_source == "ted":
                        ted_limit = limit
                        ted_offset = offset
                    else:
                        ted_limit = max(1, limit // 3)
                        ted_offset = 0
                    rows_ted = (
                        qry_ted.order_by(TenderMatch.match_score.desc())
                        .offset(ted_offset)
                        .limit(ted_limit)
                        .all()
                    )
                    bucket_ted = [
                        {
                            **_serialise_ted(t),
                            "match_score": float(m.match_score) if m.match_score else None,
                            "is_saved": bool(m.is_saved),
                            "is_applied": bool(m.is_applied),
                            "match_id": m.id,
                        }
                        for m, t in rows_ted
                    ]

                # --- F&T proposals: on-the-fly keyword scoring ---
                if match_source in ("all", "ft_proposals"):
                    qry_prop = db.query(FtCallForProposals).filter(
                        FtCallForProposals.is_test == False,  # noqa: E712
                        # Matches are actionable opportunities: hide passed deadlines.
                        or_(FtCallForProposals.deadline >= now, FtCallForProposals.deadline.is_(None)),
                    )
                    if q:
                        qry_prop = qry_prop.filter(FtCallForProposals.title.ilike(f"%{q}%"))
                    rows_prop = qry_prop.all() if kw_lower else []
                    scored: List[Tuple[float, Any]] = []
                    for p in rows_prop:
                        title_l = (p.title or "").lower()
                        desc_l = (p.description or "").lower()
                        score = 0.0
                        for kw in kw_lower:
                            if kw in title_l:
                                score += 40
                            elif kw in desc_l:
                                score += 20
                        # Open status earns bonus
                        if p.status and p.status.lower() == "open":
                            score += 10
                        if score >= 20:
                            scored.append((score, p))
                    scored.sort(key=lambda x: x[0], reverse=True)
                    total_proposal_matches = len(scored)
                    take_offset = offset if match_source == "ft_proposals" else 0
                    take_limit = limit if match_source == "ft_proposals" else max(1, limit // 3)
                    bucket_proposals = [
                        {
                            **_serialise_proposal(p),
                            "match_score": float(score),
                            "is_saved": False,
                            "is_applied": False,
                        }
                        for (score, p) in scored[take_offset : take_offset + take_limit]
                    ]

                # --- F&T tenders: on-the-fly CPV + keyword + country scoring ---
                if match_source in ("all", "ft_tenders"):
                    qry_tend = db.query(FtCallForTenders).filter(
                        FtCallForTenders.is_test == False,  # noqa: E712
                        or_(FtCallForTenders.deadline >= now, FtCallForTenders.deadline.is_(None)),
                    )
                    if q:
                        qry_tend = qry_tend.filter(FtCallForTenders.title.ilike(f"%{q}%"))
                    rows_tend = qry_tend.all() if (kw_lower or cpv_two or countries) else []
                    scored: List[Tuple[float, Any]] = []
                    for ftt in rows_tend:
                        title_l = (ftt.title or "").lower()
                        desc_l = (ftt.description or "").lower()
                        cpv_list = ftt.cpv_codes or []
                        score = 0.0
                        if cpv_two:
                            for c in cpv_list:
                                if c and c[:2] in cpv_two:
                                    score += 40
                                    break
                        for kw in kw_lower:
                            if kw in title_l:
                                score += 30
                            elif kw in desc_l:
                                score += 15
                        # Country boost via contracting_authority text
                        if countries and ftt.contracting_authority:
                            ca_lower = ftt.contracting_authority.lower()
                            if any(c.lower() in ca_lower for c in countries):
                                score += 10
                        if score >= 20:
                            scored.append((score, ftt))
                    scored.sort(key=lambda x: x[0], reverse=True)
                    total_tender_matches = len(scored)
                    take_offset = offset if match_source == "ft_tenders" else 0
                    take_limit = limit if match_source == "ft_tenders" else max(1, limit // 3)
                    bucket_tenders = [
                        {
                            **_serialise_tender_ft(t),
                            "match_score": float(score),
                            "is_saved": False,
                            "is_applied": False,
                        }
                        for (score, t) in scored[take_offset : take_offset + take_limit]
                    ]

                # --- Agency: on-the-fly keyword scoring over economy_items ---
                # No CPV, country, budget on the row → only keyword + deadline
                # signal contribute. Same threshold as the other buckets so a
                # noisy agency feed never floods the "your matches" view.
                if match_source in ("all", "agency"):
                    agency_rows = []
                    if kw_lower:
                        try:
                            agency_rows = db.execute(
                                _sql_text(
                                    "SELECT id, body_code, item_type, title, summary, "
                                    "       public_url, document_date, creation_date, detected_lang "
                                    "FROM economy_items "
                                    "WHERE item_type = ANY(:types) "
                                    "  AND (document_date >= :now OR document_date IS NULL) "
                                    "  AND " + (
                                        # ILIKE q if provided, no-op otherwise
                                        "(title ILIKE :q OR summary ILIKE :q) " if q else "TRUE "
                                    )
                                ),
                                {"types": list(_AGENCY_ITEM_TYPES), "now": now,
                                 **({"q": f"%{q}%"} if q else {})},
                            ).fetchall()
                        except Exception as exc:
                            logger.warning("matches agency-rows fetch failed: %s", exc)
                            db.rollback()
                            agency_rows = []
                    scored: List[Tuple[float, Any]] = []
                    for ar in agency_rows:
                        title_l = (ar.title or "").lower()
                        sum_l = (ar.summary or "").lower()
                        score = 0.0
                        for kw in kw_lower:
                            if kw in title_l:
                                score += 35
                            elif kw in sum_l:
                                score += 18
                        # Open status is implied (deadline filter already
                        # excluded passed deadlines), so add a small bonus
                        # only when the deadline is comfortably in the future.
                        if ar.document_date:
                            days_left = (ar.document_date.replace(tzinfo=None) - now).days
                            if days_left >= 14:
                                score += 5
                        if score >= 20:
                            scored.append((score, ar))
                    scored.sort(key=lambda x: x[0], reverse=True)
                    total_agency_matches = len(scored)
                    take_offset = offset if match_source == "agency" else 0
                    take_limit = limit if match_source == "agency" else max(1, limit // 4)
                    bucket_agency = [
                        {
                            **_serialise_agency(ar),
                            "match_score": float(score),
                            "is_saved": False,
                            "is_applied": False,
                        }
                        for (score, ar) in scored[take_offset : take_offset + take_limit]
                    ]

                if match_source == "ted":
                    items = bucket_ted
                elif match_source == "ft_proposals":
                    items = bucket_proposals
                elif match_source == "ft_tenders":
                    items = bucket_tenders
                elif match_source == "agency":
                    items = bucket_agency
                else:
                    # "all" inside matches: interleave the four buckets, sort
                    # by match_score desc, take top `limit`.
                    combined = bucket_ted + bucket_proposals + bucket_tenders + bucket_agency
                    combined.sort(key=lambda x: (x.get("match_score") or 0), reverse=True)
                    items = combined[:limit]

                items = _overlay_translations(items)
                return {
                    "source": source,
                    "match_source": match_source,
                    "page": page,
                    "limit": limit,
                    "totals": {
                        "ted": total_ted_matches,
                        "ft_proposals": total_proposal_matches,
                        "ft_tenders": total_tender_matches,
                        "ft_projects": 0,
                        "agency": total_agency_matches,
                    },
                    "items": items,
                    "personalised_applied": personalised_applied,
                    "personalised_requested": personalised,
                    "interests": interests if personalised_applied else [],
                    "interest_count": len(interests) if personalised_applied else 0,
                }
            except Exception as exc:
                logger.error(f"matches feed failed: {exc}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"Matches query failed: {exc}")

        if source == "ted" or source == "all":
            qry = _ted_query()
            totals["ted"] = qry.count()
            if source == "ted":
                rows = qry.order_by(Tender.submission_deadline.asc().nullslast()).offset(offset).limit(limit).all()
                items.extend(_serialise_ted(t) for t in rows)
        if source == "ft_proposals" or source == "all":
            qry = _proposals_query()
            totals["ft_proposals"] = qry.count()
            if source == "ft_proposals":
                rows = qry.order_by(FtCallForProposals.deadline.asc().nullslast()).offset(offset).limit(limit).all()
                items.extend(_serialise_proposal(p) for p in rows)
        if source == "ft_tenders" or source == "all":
            qry = _tenders_query()
            totals["ft_tenders"] = qry.count()
            if source == "ft_tenders":
                rows = qry.order_by(FtCallForTenders.deadline.asc().nullslast()).offset(offset).limit(limit).all()
                items.extend(_serialise_tender_ft(t) for t in rows)
        if source == "ft_projects" or source == "all":
            qry = _projects_query()
            totals["ft_projects"] = qry.count()
            if source == "ft_projects":
                rows = qry.order_by(FtFundedProject.start_date.desc().nullslast()).offset(offset).limit(limit).all()
                items.extend(_serialise_project(p) for p in rows)
        if source == "agency" or source == "all":
            totals["agency"] = _agency_count()
            if source == "agency":
                rows = _agency_rows(offset, limit)
                items.extend(_serialise_agency(r) for r in rows)
        # External-action awards source (FTS) — only counted/loaded when
        # the lens is on or the user explicitly picks source=intl_coop.
        # In the default 'all' view we skip it (too noisy alongside live
        # opportunities); the lens elevates it.
        load_intl = (source == "intl_coop") or (source == "all" and external_action)
        if load_intl:
            totals["intl_coop"] = _intl_coop_count()
            if source == "intl_coop":
                rows = _intl_coop_rows(offset, limit)
                items.extend(_serialise_intl_coop(r) for r in rows)

        # 'all' mode: interleave the top N from each source so the user sees
        # the variety. Five live sources + intl_coop when the lens is on.
        if source == "all":
            slot_count = 6 if external_action else 5
            per_source = max(1, limit // slot_count)
            slot_ted = _ted_query().order_by(Tender.submission_deadline.asc().nullslast()).offset(offset).limit(per_source).all()
            slot_prop = _proposals_query().order_by(FtCallForProposals.deadline.asc().nullslast()).offset(offset).limit(per_source).all()
            slot_tend = _tenders_query().order_by(FtCallForTenders.deadline.asc().nullslast()).offset(offset).limit(per_source).all()
            slot_proj = _projects_query().order_by(FtFundedProject.start_date.desc().nullslast()).offset(offset).limit(per_source).all()
            slot_agency = _agency_rows(offset, per_source)
            items = []
            items.extend(_serialise_ted(t) for t in slot_ted)
            items.extend(_serialise_proposal(p) for p in slot_prop)
            items.extend(_serialise_tender_ft(t) for t in slot_tend)
            items.extend(_serialise_project(p) for p in slot_proj)
            items.extend(_serialise_agency(r) for r in slot_agency)
            if external_action:
                slot_intl = _intl_coop_rows(offset, per_source)
                items.extend(_serialise_intl_coop(r) for r in slot_intl)
    except Exception as exc:
        logger.error(f"unified-feed query failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Feed query failed: {str(exc)}",
        )

    items = _overlay_translations(items)
    return {
        "source": source,
        "page": page,
        "limit": limit,
        "totals": totals,
        "items": items,
        "client_filter_applied": bool(pursuits),
        "client_filter_slug": current_user.private_guide_slug if (client_filter and pursuits) else None,
        "personalised_applied": personalised_applied,
        "personalised_requested": personalised,
        "interests": interests if personalised_applied else [],
        "interest_count": len(interests) if personalised_applied else 0,
        "external_action_applied": external_action,
        "beneficiary_country": beneficiary_country,
    }


# ============================================================================
# Step 5: Bodies catalogue (the EU agencies feeding economy_items funding rows)
# ============================================================================

_BODY_DISPLAY_NAMES = {
    "efca": "European Fisheries Control Agency",
    "cedefop": "European Centre for the Development of Vocational Training",
    "ema": "European Medicines Agency",
    "efsa": "European Food Safety Authority",
    "eurojust": "European Union Agency for Criminal Justice Cooperation",
    "etf": "European Training Foundation",
    "eige": "European Institute for Gender Equality",
    "euaa": "European Union Agency for Asylum",
    "fra": "European Union Agency for Fundamental Rights",
    "era": "European Union Agency for Railways",
    "eurofound": "European Foundation for the Improvement of Living and Working Conditions",
    "eea": "European Environment Agency",
    "echa": "European Chemicals Agency",
    "euda": "European Union Drugs Agency",
    "ecdc": "European Centre for Disease Prevention and Control",
    "enisa": "European Union Agency for Cybersecurity",
    "eu_osha": "European Agency for Safety and Health at Work",
    "commission": "European Commission",
    "innovfund": "EU Innovation Fund",
    "just": "Justice Programme (DG JUST)",
    "eib": "European Investment Bank",
    "eeas": "European External Action Service",
    "parliament": "European Parliament",
    "council": "Council of the European Union",
    "ecb": "European Central Bank",
}

_BODY_DISPLAY_ACRONYMS = {
    "efca": "EFCA", "cedefop": "Cedefop", "ema": "EMA", "efsa": "EFSA",
    "eurojust": "Eurojust", "etf": "ETF", "eige": "EIGE", "euaa": "EUAA",
    "fra": "FRA", "era": "ERA", "eurofound": "Eurofound", "eea": "EEA",
    "echa": "ECHA", "euda": "EUDA", "ecdc": "ECDC", "enisa": "ENISA",
    "eu_osha": "EU-OSHA", "commission": "EC",
    "innovfund": "Innovation Fund", "just": "DG JUST", "eib": "EIB",
    "eeas": "EEAS", "parliament": "EP", "council": "Council", "ecb": "ECB",
}


# ============================================================================
# Move 4 (15 Jun 2026): Pipeline CRM — generic over every Tenderator source
# ============================================================================

_PIPELINE_STATUSES = (
    "lead", "drafting", "submitted", "awarded",
    "executing", "paid", "lost", "cancelled",
)


class _PipelineCreate(_PydanticBaseModel):
    """Body for POST /api/tenders/pipeline — add an opportunity to the
    pipeline. opportunity_id MUST be source-qualified ('ted:123',
    'ft_proposals:uuid', 'intl_coop:456', etc.)."""
    opportunity_id: str
    source: str
    title: str
    organisation: Optional[str] = None
    country: Optional[str] = None
    programme: Optional[str] = None
    deadline: Optional[datetime] = None
    budget: Optional[float] = None
    currency: Optional[str] = "EUR"
    source_url: Optional[str] = None
    status: Optional[str] = "lead"
    next_step: Optional[str] = None
    next_step_due: Optional[str] = None  # YYYY-MM-DD
    pm_assignee: Optional[str] = None
    notes: Optional[str] = None


class _PipelineUpdate(_PydanticBaseModel):
    """Body for PUT /api/tenders/pipeline/{id} — partial update."""
    status: Optional[str] = None
    next_step: Optional[str] = None
    next_step_due: Optional[str] = None
    pm_assignee: Optional[str] = None
    notes: Optional[str] = None


@router.get(
    "/pipeline",
    summary="List my pipeline opportunities",
    description=(
        "Returns all opportunities the current user has added to their "
        "pipeline, across every Tenderator source (TED, F&T proposals, "
        "F&T tenders, F&T projects, agency, intl_coop). Sorted by "
        "next_step_due ASC then deadline ASC. Filter by `status` to get "
        "a single pipeline column. Blue tier only."
    ),
)
async def list_pipeline(
    status_filter: Optional[str] = Query(None, alias="status", description="lead | drafting | submitted | awarded | executing | paid | lost | cancelled"),
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    from models.tender import TenderPipeline
    qry = db.query(TenderPipeline).filter(TenderPipeline.user_id == current_user.id)
    if status_filter:
        if status_filter not in _PIPELINE_STATUSES:
            raise HTTPException(status_code=400,
                detail=f"status must be one of {list(_PIPELINE_STATUSES)}")
        qry = qry.filter(TenderPipeline.status == status_filter)
    rows = qry.order_by(
        TenderPipeline.next_step_due.asc().nullslast(),
        TenderPipeline.deadline.asc().nullslast(),
        TenderPipeline.updated_at.desc(),
    ).all()
    # Aggregate counts per status across the user's full pipeline (always).
    from sqlalchemy import func as _sql_func
    counts = dict(
        db.query(TenderPipeline.status, _sql_func.count(TenderPipeline.id))
          .filter(TenderPipeline.user_id == current_user.id)
          .group_by(TenderPipeline.status).all()
    )
    return {
        "items": [r.to_dict() for r in rows],
        "counts": {s: int(counts.get(s, 0)) for s in _PIPELINE_STATUSES},
        "statuses": list(_PIPELINE_STATUSES),
    }


@router.post(
    "/pipeline",
    status_code=status.HTTP_201_CREATED,
    summary="Add an opportunity to my pipeline",
    description=(
        "Snapshots an opportunity at add-time and starts tracking it. The "
        "default status is 'lead'. Idempotent — re-posting the same "
        "opportunity_id updates the snapshot fields instead of erroring."
    ),
)
async def add_to_pipeline(
    body: _PipelineCreate,
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    from models.tender import TenderPipeline
    if body.status and body.status not in _PIPELINE_STATUSES:
        raise HTTPException(status_code=400,
            detail=f"status must be one of {list(_PIPELINE_STATUSES)}")
    # Parse next_step_due
    due = None
    if body.next_step_due:
        try:
            due = datetime.fromisoformat(body.next_step_due).date()
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="next_step_due must be YYYY-MM-DD")
    existing = db.query(TenderPipeline).filter(
        TenderPipeline.user_id == current_user.id,
        TenderPipeline.opportunity_id == body.opportunity_id,
    ).first()
    if existing:
        # Idempotent: refresh snapshot + status if provided
        existing.title = body.title or existing.title
        existing.organisation = body.organisation or existing.organisation
        existing.country = body.country or existing.country
        existing.programme = body.programme or existing.programme
        existing.deadline = body.deadline or existing.deadline
        existing.budget = body.budget if body.budget is not None else existing.budget
        existing.currency = body.currency or existing.currency
        existing.source_url = body.source_url or existing.source_url
        if body.status:
            existing.status = body.status
        if body.next_step is not None:
            existing.next_step = body.next_step
        if due is not None:
            existing.next_step_due = due
        if body.pm_assignee is not None:
            existing.pm_assignee = body.pm_assignee
        if body.notes is not None:
            existing.notes = body.notes
        db.commit()
        db.refresh(existing)
        return existing.to_dict()
    row = TenderPipeline(
        user_id=current_user.id,
        opportunity_id=body.opportunity_id,
        source=body.source,
        title=body.title,
        organisation=body.organisation,
        country=body.country,
        programme=body.programme,
        deadline=body.deadline,
        budget=body.budget,
        currency=body.currency or "EUR",
        source_url=body.source_url,
        status=body.status or "lead",
        next_step=body.next_step,
        next_step_due=due,
        pm_assignee=body.pm_assignee,
        notes=body.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.put(
    "/pipeline/{pipeline_id}",
    summary="Update a pipeline row",
    description="Partial update of status / next step / assignee / notes.",
)
async def update_pipeline(
    pipeline_id: int,
    body: _PipelineUpdate,
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    from models.tender import TenderPipeline
    row = db.query(TenderPipeline).filter(
        TenderPipeline.id == pipeline_id,
        TenderPipeline.user_id == current_user.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline row not found")
    if body.status is not None:
        if body.status not in _PIPELINE_STATUSES:
            raise HTTPException(status_code=400,
                detail=f"status must be one of {list(_PIPELINE_STATUSES)}")
        row.status = body.status
    if body.next_step is not None:
        row.next_step = body.next_step
    if body.next_step_due is not None:
        if body.next_step_due == "":
            row.next_step_due = None
        else:
            try:
                row.next_step_due = datetime.fromisoformat(body.next_step_due).date()
            except (ValueError, AttributeError):
                raise HTTPException(status_code=400, detail="next_step_due must be YYYY-MM-DD")
    if body.pm_assignee is not None:
        row.pm_assignee = body.pm_assignee
    if body.notes is not None:
        row.notes = body.notes
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.delete(
    "/pipeline/{pipeline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a pipeline row",
)
async def delete_pipeline(
    pipeline_id: int,
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    from models.tender import TenderPipeline
    row = db.query(TenderPipeline).filter(
        TenderPipeline.id == pipeline_id,
        TenderPipeline.user_id == current_user.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline row not found")
    db.delete(row)
    db.commit()
    return None


@router.get(
    "/bodies",
    summary="EU agencies feeding the Tenderator's decentralised-procurement source",
    description=(
        "Returns the catalogue of EU agencies / bodies that contribute "
        "tenders, grants and calls for expression of interest to the "
        "Tenderator's `source=agency` view, with an open-opportunities "
        "count per body. Powers the right-rail BodiesPanel. Anyone with "
        "Blue tier can call it."
    ),
)
async def get_bodies(
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    try:
        rows = db.execute(
            text(
                "SELECT body_code, count(*) AS total, "
                "       count(*) FILTER (WHERE document_date > :now OR document_date IS NULL) AS open_count "
                "FROM economy_items "
                "WHERE item_type = ANY(:types) "
                "GROUP BY body_code "
                "ORDER BY open_count DESC NULLS LAST, total DESC"
            ),
            {"types": ["tender", "grant", "eoi_call", "startup_funding", "framework"], "now": now},
        ).fetchall()
    except Exception as exc:
        logger.warning("get_bodies failed: %s", exc)
        db.rollback()
        rows = []

    items = []
    for r in rows:
        items.append({
            "body_code": r.body_code,
            "acronym": _BODY_DISPLAY_ACRONYMS.get(r.body_code, r.body_code.upper()),
            "name": _BODY_DISPLAY_NAMES.get(r.body_code, r.body_code),
            "total": int(r.total or 0),
            "open_count": int(r.open_count or 0),
        })
    return {"items": items, "generated_at": now.isoformat()}


# ============================================================================
# Dashboard cockpit endpoint
# ============================================================================

@router.get(
    "/dashboard-stats",
    summary="Cockpit metrics for the Tenderator dashboard",
    description=(
        "Returns the 5 top-strip KPIs plus the closing-soon urgency list "
        "and per-source counts. Pure aggregation over `tenders`, "
        "`tender_matches`, and the three F&T tables. Blue tier only."
    ),
)
async def get_dashboard_stats(
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    """
    KPI strip cards consumed by tenderator_dashboard.tsx:
      - open_opportunities: open tenders across all sources
      - closing_7d:         count of saved or matched items whose deadline
                            falls in the next 7 days
      - your_matches:       total tender_matches for this user
      - your_saved:         saved tender_matches for this user
      - applied_ytd:        applied tender_matches for this user this year

    Plus:
      - deltas_week_over_week for matches and saved
      - closing_soon: top 5 deadlines in the next 14 days
      - by_source: { ted, ft_proposals, ft_tenders, ft_projects }
    """
    from datetime import timedelta
    from sqlalchemy import func
    from models.funding_tenders import (
        FtCallForProposals,
        FtCallForTenders,
        FtFundedProject,
    )

    user_id = current_user.id
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    in_7_days = now + timedelta(days=7)
    in_14_days = now + timedelta(days=14)
    year_start = datetime(now.year, 1, 1)

    def _safe(query_fn, default=0):
        try:
            return query_fn()
        except Exception as exc:
            logger.warning("dashboard-stats sub-query failed: %s", exc)
            db.rollback()
            return default

    # --- per-source open-opportunity counts ---
    ted_open = _safe(lambda: db.query(Tender).filter(
        (Tender.submission_deadline > now) | (Tender.submission_deadline.is_(None))
    ).count())
    ft_proposals_open = _safe(lambda: db.query(FtCallForProposals).filter(
        FtCallForProposals.is_test == False,
        (FtCallForProposals.deadline > now) | (FtCallForProposals.deadline.is_(None)),
    ).count())
    ft_tenders_open = _safe(lambda: db.query(FtCallForTenders).filter(
        FtCallForTenders.is_test == False,
        (FtCallForTenders.deadline > now) | (FtCallForTenders.deadline.is_(None)),
    ).count())
    ft_projects_total = _safe(lambda: db.query(FtFundedProject).filter(
        FtFundedProject.is_test == False,
    ).count())

    # Agency procurement (economy_items) — same store the public
    # /api/v2/funding/{agency}-* endpoints serve. Open = deadline in the future
    # or unknown.
    agency_open = _safe(lambda: db.execute(
        text(
            "SELECT count(*) FROM economy_items "
            "WHERE item_type = ANY(:types) "
            "  AND (document_date > :now OR document_date IS NULL)"
        ),
        {"types": ["tender", "grant", "eoi_call", "startup_funding"], "now": now},
    ).scalar() or 0)

    open_opportunities = ted_open + ft_proposals_open + ft_tenders_open + agency_open

    # --- per-user pipeline counts ---
    total_matches = _safe(lambda: db.query(TenderMatch).filter(
        TenderMatch.user_id == user_id
    ).count())
    your_saved = _safe(lambda: db.query(TenderMatch).filter(
        TenderMatch.user_id == user_id,
        TenderMatch.is_saved == True,
    ).count())
    applied_ytd = _safe(lambda: db.query(TenderMatch).filter(
        TenderMatch.user_id == user_id,
        TenderMatch.is_applied == True,
        TenderMatch.created_at >= year_start,
    ).count())

    matches_this_week = _safe(lambda: db.query(TenderMatch).filter(
        TenderMatch.user_id == user_id,
        TenderMatch.created_at >= week_ago,
    ).count())
    matches_prev_week = _safe(lambda: db.query(TenderMatch).filter(
        TenderMatch.user_id == user_id,
        TenderMatch.created_at >= two_weeks_ago,
        TenderMatch.created_at < week_ago,
    ).count())

    saved_this_week = _safe(lambda: db.query(TenderMatch).filter(
        TenderMatch.user_id == user_id,
        TenderMatch.is_saved == True,
        TenderMatch.created_at >= week_ago,
    ).count())
    saved_prev_week = _safe(lambda: db.query(TenderMatch).filter(
        TenderMatch.user_id == user_id,
        TenderMatch.is_saved == True,
        TenderMatch.created_at >= two_weeks_ago,
        TenderMatch.created_at < week_ago,
    ).count())

    # --- closing in next 7d (saved or matched) ---
    closing_7d_q = (
        db.query(TenderMatch, Tender)
        .join(Tender, Tender.id == TenderMatch.tender_id)
        .filter(TenderMatch.user_id == user_id)
        .filter(Tender.submission_deadline != None)
        .filter(Tender.submission_deadline >= now)
        .filter(Tender.submission_deadline <= in_7_days)
    )
    closing_7d_count = _safe(lambda: closing_7d_q.count())

    closing_soon = []
    try:
        rows = (
            db.query(TenderMatch, Tender)
            .join(Tender, Tender.id == TenderMatch.tender_id)
            .filter(TenderMatch.user_id == user_id)
            .filter(Tender.submission_deadline != None)
            .filter(Tender.submission_deadline >= now)
            .filter(Tender.submission_deadline <= in_14_days)
            .order_by(Tender.submission_deadline.asc())
            .limit(5)
            .all()
        )
        for m, t in rows:
            # Normalise tz so the subtraction does not blow up. The DB column
            # is tz-aware; `now = datetime.utcnow()` is tz-naive.
            deadline = t.submission_deadline
            if deadline.tzinfo is not None:
                deadline = deadline.replace(tzinfo=None)
            days_left = max(0, (deadline - now).days)
            closing_soon.append({
                "tender_id": t.id,
                "match_id": m.id,
                "publication_number": t.publication_number,
                "title": (t.title or "")[:120],
                "deadline": t.submission_deadline.isoformat() if t.submission_deadline else None,
                "days_left": days_left,
                "estimated_value": float(t.estimated_value) if t.estimated_value else None,
                "currency": getattr(t, "estimated_value_currency", None) or "EUR",
                "source": "ted",
            })
    except Exception as exc:
        logger.warning("dashboard-stats closing_soon failed: %s", exc)
        db.rollback()

    return {
        "kpis": {
            "open_opportunities": open_opportunities,
            "closing_7d": closing_7d_count,
            "your_matches": total_matches,
            "your_saved": your_saved,
            "applied_ytd": applied_ytd,
        },
        "deltas": {
            "matches_wow": matches_this_week - matches_prev_week,
            "saved_wow": saved_this_week - saved_prev_week,
            "matches_this_week": matches_this_week,
            "saved_this_week": saved_this_week,
        },
        "by_source": {
            "ted": ted_open,
            "ft_proposals": ft_proposals_open,
            "ft_tenders": ft_tenders_open,
            "ft_projects": ft_projects_total,
            "agency": agency_open,
        },
        "closing_soon": closing_soon,
        "generated_at": now.isoformat(),
    }


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
    from services.eu_law_search import EULawSearchService

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

**Language**: Always respond in clear British English, regardless of the
source language. The tender text below may be in any EU language (e.g.
Croatian, Polish, Hungarian, Greek, German, Spanish, Italian). If you
see non-English text, translate the key facts before summarising — do
NOT echo the original language.

Tender Information:
{tender_context}

Provide your response in this exact JSON format:
{{
    "en_title": "The TENDER TITLE translated to clear British English, exactly preserving meaning. If the title was already English, repeat it verbatim.",
    "one_liner": "A single sentence describing the opportunity, in English",
    "what": "What is being procured (2-3 sentences max), in English. Translate from the source language if needed.",
    "who": "Brief description of the contracting authority, in English",
    "value": "Contract value or budget information",
    "deadline": "Submission deadline with any important time notes",
    "key_requirements": ["First concrete requirement", "Second concrete requirement", "Third concrete requirement"],
    "award_focus": "What the evaluation criteria prioritise, in English"
}}

Respond ONLY with the JSON, no additional text."""

        try:
            from services.ai_service import get_ai_service
            import json
            import re

            ai_service = get_ai_service()
            # use_context=False — the tender summary doesn't need the 19k-char
            # Brubru EU KB; including it blew the Cerebras 60K TPM budget and
            # made the endpoint hang >180s on prod. The brief endpoint already
            # uses this flag. The tender_context above carries all the data
            # the AI needs.
            response = await ai_service.chat(
                user_message=prompt,
                conversation_history=[],
                user_id=str(current_user.id),
                use_context=False,
                stream=False,
                is_pre_user=False,
            )

            # Extract JSON from response with robust parsing
            response_text = response.message if hasattr(response, "message") else (
                response.get("response", "") if isinstance(response, dict) else str(response)
            )
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


_BRUBRU_LANGS = {"en", "es", "ca", "fr", "it", "nl"}


def _fallback_translate(text: str, src_lang: Optional[str]) -> str:
    """Best-effort English translation for the fallback summary when the AI
    summary path failed. Avoids dumping raw Croatian / Polish / Greek
    description into the WHAT field. Tries the cached sidecar first; if
    nothing is cached, returns the source text with a clear hint."""
    if not text:
        return ""
    if not src_lang or src_lang in _BRUBRU_LANGS:
        return text
    return f"[Original in {src_lang.upper()} (open the source notice for the full text).] {text[:240]}..."


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

    # Source language detection — Croatian / Polish / Hungarian etc.
    # often produce a fallback summary; we don't want raw non-English to
    # leak as the "WHAT" field.
    src_lang = getattr(tender, "detected_lang", None)

    if tender.description and len(tender.description) > 300:
        what_str = _fallback_translate(tender.description[:300] + "...", src_lang)
    elif tender.description:
        what_str = _fallback_translate(tender.description, src_lang)
    else:
        what_str = "See tender notice for details."

    one_liner = _fallback_translate(tender.title, src_lang) if tender.title else "EU public procurement opportunity"
    # en_title: in the fallback we don't have a translation, so we either
    # echo the original (when it's already in Brubru-6) or flag the source
    # language for the UI to render a 'translated from X' badge.
    en_title = tender.title if (not src_lang or src_lang in _BRUBRU_LANGS) else None

    return {
        "en_title": en_title,
        "one_liner": one_liner,
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
    from services.eu_law_search import EULawSearchService

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


# ============================================================================
# Layer 3: Client scorecard endpoint
# ============================================================================

@router.get(
    "/scorecard/client",
    summary="Win-rate and lookalike-bid intel for the authenticated client",
    description=(
        "Returns the user's private win-rate scorecard, decorated against the "
        "opportunity context they're viewing. Reads client_submissions rows "
        "keyed on private_guide_slug. Requires a configured private guide."
        "\n\n"
        "**Inputs (all optional, used to find lookalikes):** ca, country, "
        "programme, lot, keyword.\n\n"
        "**Returns:** overall counters, win-rate by leading partner, win-rate "
        "by CA, top-N lookalike past bids with outcome and comments. Blue tier."
    ),
)
async def get_client_scorecard(
    ca: Optional[str] = Query(None, description="Contracting authority substring"),
    country: Optional[str] = Query(None),
    programme: Optional[str] = Query(None),
    lot: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None, description="Substring on project_title"),
    lookalike_limit: int = Query(3, ge=1, le=10),
    current_user: User = Depends(require_blue_tier),
    db: Session = Depends(get_db),
):
    try:
        return await _client_scorecard_impl(ca, country, programme, lot, keyword, lookalike_limit, current_user, db)
    except Exception as exc:
        import traceback
        logger.error("client-scorecard 500: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"client-scorecard failed: {type(exc).__name__}: {str(exc)[:300]}")


async def _client_scorecard_impl(ca, country, programme, lot, keyword, lookalike_limit, current_user, db):
    from sqlalchemy import text as _sql_text

    slug = getattr(current_user, "private_guide_slug", None)
    if not slug:
        return {
            "slug": None,
            "scorecard_available": False,
            "reason": "User has no private_guide_slug; no scorecard data.",
        }

    overall = db.execute(_sql_text(
        "SELECT outcome, COUNT(*) FROM client_submissions "
        "WHERE slug=:slug AND is_test=FALSE GROUP BY outcome"
    ), {"slug": slug}).fetchall()
    overall_map = {r[0]: int(r[1]) for r in overall}
    total = sum(overall_map.values())
    if total == 0:
        return {
            "slug": slug,
            "scorecard_available": False,
            "reason": "No client_submissions on file for this slug.",
        }

    awarded = overall_map.get("awarded", 0)
    lost = overall_map.get("not_awarded", 0)
    pending = overall_map.get("pending", 0)
    cancelled = overall_map.get("cancelled", 0)
    decided = awarded + lost
    overall_win_rate_pct = round(awarded / decided * 100, 1) if decided else None

    by_lead = db.execute(_sql_text(
        "SELECT leading_partner, "
        "SUM(CASE WHEN outcome='awarded' THEN 1 ELSE 0 END) AS awarded, "
        "SUM(CASE WHEN outcome='not_awarded' THEN 1 ELSE 0 END) AS lost, "
        "SUM(CASE WHEN outcome='pending' THEN 1 ELSE 0 END) AS pending "
        "FROM client_submissions "
        "WHERE slug=:slug AND is_test=FALSE AND leading_partner IS NOT NULL "
        "GROUP BY leading_partner "
        "ORDER BY COUNT(*) DESC "
        "LIMIT 12"
    ), {"slug": slug}).fetchall()
    lead_rows = []
    for r in by_lead:
        a, l, p = int(r[1] or 0), int(r[2] or 0), int(r[3] or 0)
        d = a + l
        lead_rows.append({
            "leading_partner": r[0],
            "awarded": a, "lost": l, "pending": p,
            "win_rate_pct": round(a/d*100, 1) if d else None,
        })

    by_ca = db.execute(_sql_text(
        "SELECT contracting_authority, "
        "SUM(CASE WHEN outcome='awarded' THEN 1 ELSE 0 END) AS awarded, "
        "SUM(CASE WHEN outcome='not_awarded' THEN 1 ELSE 0 END) AS lost, "
        "SUM(CASE WHEN outcome='pending' THEN 1 ELSE 0 END) AS pending "
        "FROM client_submissions "
        "WHERE slug=:slug AND is_test=FALSE AND contracting_authority IS NOT NULL "
        "GROUP BY contracting_authority "
        "ORDER BY COUNT(*) DESC"
    ), {"slug": slug}).fetchall()
    ca_rows = []
    for r in by_ca:
        a, l, p = int(r[1] or 0), int(r[2] or 0), int(r[3] or 0)
        d = a + l
        ca_rows.append({
            "contracting_authority": r[0],
            "awarded": a, "lost": l, "pending": p,
            "win_rate_pct": round(a/d*100, 1) if d else None,
        })

    conds = ["slug=:slug", "is_test=FALSE"]
    params = {"slug": slug, "lim": lookalike_limit}
    if ca:
        conds.append("contracting_authority ILIKE :ca"); params["ca"] = f"%{ca}%"
    if country:
        conds.append("country ILIKE :country"); params["country"] = f"%{country}%"
    if programme:
        conds.append("programme ILIKE :programme"); params["programme"] = f"%{programme}%"
    if lot:
        conds.append("lot ILIKE :lot"); params["lot"] = f"%{lot}%"
    if keyword:
        conds.append("project_title ILIKE :keyword"); params["keyword"] = f"%{keyword}%"

    sql = (
        "SELECT id, project_title, contracting_authority, country, programme, lot, "
        "outcome, comments, submission_date, leading_partner, budget_eur "
        "FROM client_submissions WHERE " + " AND ".join(conds) + " "
        "ORDER BY submission_date DESC NULLS LAST LIMIT :lim"
    )
    lookalike_rows = db.execute(_sql_text(sql), params).fetchall()
    lookalikes = [
        {
            "id": str(r[0]),
            "project_title": r[1],
            "contracting_authority": r[2],
            "country": r[3],
            "programme": r[4],
            "lot": r[5],
            "outcome": r[6],
            "comments": r[7],
            "submission_date": r[8].isoformat() if r[8] else None,
            "leading_partner": r[9],
            "budget_eur": float(r[10]) if r[10] is not None else None,
        }
        for r in lookalike_rows
    ]

    return {
        "slug": slug,
        "scorecard_available": True,
        "overall": {
            "total": total,
            "awarded": awarded,
            "not_awarded": lost,
            "pending": pending,
            "cancelled": cancelled,
            "decided": decided,
            "win_rate_pct": overall_win_rate_pct,
        },
        "by_leading_partner": lead_rows,
        "by_contracting_authority": ca_rows,
        "lookalikes": lookalikes,
        "filters_used": {k: v for k, v in {"ca": ca, "country": country, "programme": programme, "lot": lot, "keyword": keyword}.items() if v},
    }
