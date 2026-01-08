"""
Admin Tenders API

Administrative endpoints for managing Tenderator feature.
Requires admin role authentication.

Endpoints:
- GET /api/admin/tenders - List all tenders with filters
- GET /api/admin/tenders/{id} - Get tender details (admin view)
- PUT /api/admin/tenders/{id} - Update tender metadata
- DELETE /api/admin/tenders/{id} - Delete tender from database
- POST /api/admin/tenders/fetch - Trigger manual fetch job
- POST /api/admin/tenders/fetch-sparql - Trigger SPARQL historical load
- GET /api/admin/tenders/stats - Admin statistics dashboard
- GET /api/admin/tenders/fetch-logs - View fetch job logs
- GET /api/admin/tenders/matches - View all user-tender matches
- GET /api/admin/tenders/profiles - View all user tender profiles
- PUT /api/admin/tenders/settings - Update Tenderator settings
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel, Field

from ..core.database import get_db
from ..models.user import User
from ..models.tender import Tender, TenderProfile, TenderMatch, TenderFetchJob, TenderatorSettings as TenderatorSettingsModel
from ..services.tenders.tender_service import TenderService
from ..services.tenders.matcher import TenderMatcher
from ..services.tenders.tender_notifications import TenderNotificationService
from .admin_auth import get_current_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/tenders",
    tags=["Admin Tenders"]
)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class TenderAdminSummary(BaseModel):
    """Tender summary for admin list view."""
    id: int
    publication_number: str
    title: str
    official_name: Optional[str]
    buyer_country: Optional[str]
    cpv_main: Optional[str]
    estimated_value: Optional[float]
    submission_deadline: Optional[datetime]
    status: str
    sme_suitability_score: Optional[float]
    source: Optional[str]
    created_at: Optional[datetime]
    match_count: int = 0

    class Config:
        from_attributes = True


class TenderAdminUpdate(BaseModel):
    """Schema for admin tender updates."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = Field(None, description="open, closed, awarded, cancelled")
    sme_suitability_score: Optional[float] = Field(None, ge=0, le=100)
    cpv_main: Optional[str] = None
    estimated_value: Optional[float] = None
    submission_deadline: Optional[datetime] = None


class FetchJobRequest(BaseModel):
    """Request for manual fetch job."""
    days_back: int = Field(7, ge=1, le=90, description="Days to look back")
    countries: Optional[List[str]] = Field(None, description="Country codes to fetch")
    cpv_codes: Optional[List[str]] = Field(None, description="CPV codes to filter")
    max_value: float = Field(5_000_000, ge=0, description="Maximum tender value")
    source: str = Field("ted_api", description="Data source: ted_api or ted_sparql")


class TenderatorSettings(BaseModel):
    """Tenderator system settings."""
    default_max_value: float = Field(5_000_000, description="Default SME value threshold")
    fetch_frequency: str = Field("weekly", description="weekly, bi-weekly, or daily")
    enabled_countries: Optional[List[str]] = None
    enabled_cpv_codes: Optional[List[str]] = None
    auto_matching_enabled: bool = True
    auto_notifications_enabled: bool = True
    match_score_threshold: float = Field(50.0, ge=0, le=100)


class AdminTenderStats(BaseModel):
    """Admin statistics response."""
    total_tenders: int
    open_tenders: int
    closed_tenders: int
    awarded_tenders: int
    tenders_this_week: int
    tenders_by_country: Dict[str, int]
    tenders_by_sector: Dict[str, int]
    average_value: Optional[float]
    total_profiles: int
    active_profiles: int
    total_matches: int
    saved_matches: int
    fetch_jobs_count: int
    last_fetch_at: Optional[datetime]


class AdminMatchSummary(BaseModel):
    """Match summary for admin view."""
    id: int
    user_email: str
    user_name: Optional[str]
    tender_title: str
    publication_number: str
    match_score: float
    is_saved: bool
    is_dismissed: bool
    is_applied: bool
    created_at: datetime


class AdminProfileSummary(BaseModel):
    """Profile summary for admin view."""
    id: int
    user_email: str
    user_name: Optional[str]
    company_name: Optional[str]
    company_size: Optional[str]
    countries_count: int
    cpv_count: int
    match_count: int
    is_active: bool
    created_at: datetime


# ============================================================================
# Tender Management Endpoints
# ============================================================================

@router.get("", response_model=Dict[str, Any])
async def list_tenders(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None, description="Search in title"),
    country: Optional[str] = Query(None, description="Filter by country"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    cpv_prefix: Optional[str] = Query(None, description="Filter by CPV prefix"),
    min_value: Optional[float] = Query(None, description="Minimum value"),
    max_value: Optional[float] = Query(None, description="Maximum value"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="asc or desc"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    List all tenders with pagination and filters.
    """
    query = db.query(Tender)

    # Apply filters
    if search:
        query = query.filter(Tender.title.ilike(f"%{search}%"))

    if country:
        query = query.filter(Tender.buyer_country == country.upper())

    if status_filter:
        query = query.filter(Tender.status == status_filter)

    if cpv_prefix:
        query = query.filter(Tender.cpv_main.startswith(cpv_prefix))

    if min_value is not None:
        query = query.filter(Tender.estimated_value >= min_value)

    if max_value is not None:
        query = query.filter(Tender.estimated_value <= max_value)

    # Get total
    total = query.count()

    # Apply sorting
    if sort_order == "asc":
        query = query.order_by(getattr(Tender, sort_by))
    else:
        query = query.order_by(desc(getattr(Tender, sort_by)))

    # Paginate
    tenders = query.offset((page - 1) * page_size).limit(page_size).all()

    # Add match counts
    results = []
    for tender in tenders:
        match_count = db.query(TenderMatch).filter(
            TenderMatch.tender_id == tender.id
        ).count()

        results.append({
            **tender.to_summary_dict(),
            "source": tender.source,
            "created_at": tender.created_at.isoformat() if tender.created_at else None,
            "match_count": match_count
        })

    return {
        "tenders": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/{tender_id}")
async def get_tender_detail(
    tender_id: int,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed tender information (admin view).
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()

    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender {tender_id} not found"
        )

    # Get matches for this tender
    matches = db.query(TenderMatch).filter(
        TenderMatch.tender_id == tender_id
    ).all()

    match_info = []
    for match in matches:
        user = db.query(User).filter(User.id == match.user_id).first()
        match_info.append({
            "id": match.id,
            "user_email": user.email if user else "Unknown",
            "match_score": match.match_score,
            "is_saved": match.is_saved,
            "is_dismissed": match.is_dismissed,
            "created_at": match.created_at.isoformat() if match.created_at else None
        })

    return {
        **tender.to_dict(),
        "xml_content_length": len(tender.xml_content) if tender.xml_content else 0,
        "matches": match_info,
        "match_count": len(matches)
    }


@router.put("/{tender_id}")
async def update_tender(
    tender_id: int,
    updates: TenderAdminUpdate,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update tender metadata.
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()

    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender {tender_id} not found"
        )

    # Update fields
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tender, field, value)

    tender.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(tender)

    logger.info(f"Tender {tender_id} updated by admin {admin.id}")

    return tender.to_dict()


@router.delete("/{tender_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tender(
    tender_id: int,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Delete a tender and all associated matches.
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()

    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender {tender_id} not found"
        )

    publication_number = tender.publication_number

    # Cascade deletes matches automatically
    db.delete(tender)
    db.commit()

    logger.warning(f"Tender {tender_id} ({publication_number}) deleted by admin {admin.id}")

    return None


@router.post("/bulk-delete")
async def bulk_delete_tenders(
    tender_ids: List[int],
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Delete multiple tenders.
    """
    deleted_count = 0

    for tender_id in tender_ids:
        tender = db.query(Tender).filter(Tender.id == tender_id).first()
        if tender:
            db.delete(tender)
            deleted_count += 1

    db.commit()

    logger.warning(f"Bulk deleted {deleted_count} tenders by admin {admin.id}")

    return {
        "message": f"Deleted {deleted_count} tenders",
        "deleted_count": deleted_count
    }


# ============================================================================
# Fetch Job Management
# ============================================================================

@router.post("/fetch")
async def trigger_fetch_job(
    request: FetchJobRequest,
    background_tasks: BackgroundTasks,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger a tender fetch job from TED API.
    """
    service = TenderService(db)

    try:
        job = await service.fetch_new_tenders(
            days_back=request.days_back,
            countries=request.countries,
            cpv_codes=request.cpv_codes,
            max_value=request.max_value,
            source=request.source
        )

        logger.info(f"Fetch job {job.job_id} triggered by admin {admin.id}")

        return {
            "message": "Fetch job started",
            "job_id": job.job_id,
            "status": job.status,
            "source": request.source
        }

    except Exception as e:
        logger.error(f"Fetch job failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fetch job failed: {str(e)}"
        )


@router.post("/fetch-sparql")
async def trigger_sparql_fetch(
    months_back: int = Query(6, ge=1, le=12),
    countries: Optional[str] = Query(None, description="Comma-separated country codes"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Trigger SPARQL-based historical data load.
    """
    service = TenderService(db)

    country_list = countries.split(",") if countries else None

    try:
        job = await service.fetch_new_tenders(
            days_back=months_back * 30,
            countries=country_list,
            source="ted_sparql"
        )

        logger.info(f"SPARQL fetch job {job.job_id} triggered by admin {admin.id}")

        return {
            "message": "SPARQL fetch job started",
            "job_id": job.job_id,
            "status": job.status,
            "months_back": months_back
        }

    except Exception as e:
        logger.error(f"SPARQL fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SPARQL fetch failed: {str(e)}"
        )


@router.get("/fetch-logs")
async def get_fetch_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get fetch job history and logs.
    """
    query = db.query(TenderFetchJob)

    if status_filter:
        query = query.filter(TenderFetchJob.status == status_filter)

    total = query.count()

    jobs = query.order_by(desc(TenderFetchJob.created_at))\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    return {
        "jobs": [job.to_dict() for job in jobs],
        "total": total,
        "page": page,
        "page_size": page_size
    }


# ============================================================================
# Matching Management
# ============================================================================

@router.post("/run-matching")
async def run_matching(
    score_threshold: float = Query(50.0, ge=0, le=100),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Run tender matching algorithm for all users.
    """
    matcher = TenderMatcher(db, score_threshold=score_threshold)

    try:
        matches_created = await matcher.match_all_users()

        logger.info(f"Matching run by admin {admin.id}: {matches_created} matches created")

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


@router.post("/send-notifications")
async def send_notifications(
    notification_type: str = Query("weekly", description="weekly, deadline, or all"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Trigger tender notifications.
    """
    service = TenderNotificationService(db)

    try:
        if notification_type == "weekly":
            result = await service.send_weekly_digest()
        elif notification_type == "deadline":
            result = {"reminders_sent": await service.send_deadline_reminders()}
        else:
            digest = await service.send_weekly_digest()
            reminders = await service.send_deadline_reminders()
            result = {**digest, "reminders_sent": reminders}

        logger.info(f"Notifications sent by admin {admin.id}: {result}")

        return {
            "message": "Notifications sent",
            "result": result
        }

    except Exception as e:
        logger.error(f"Notification sending failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Notification failed: {str(e)}"
        )


@router.get("/matches")
async def list_all_matches(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_email: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, description="saved, dismissed, applied"),
    min_score: Optional[float] = Query(None),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    List all user-tender matches.
    """
    query = db.query(TenderMatch)

    if status_filter == "saved":
        query = query.filter(TenderMatch.is_saved == True)
    elif status_filter == "dismissed":
        query = query.filter(TenderMatch.is_dismissed == True)
    elif status_filter == "applied":
        query = query.filter(TenderMatch.is_applied == True)

    if min_score is not None:
        query = query.filter(TenderMatch.match_score >= min_score)

    # Filter by user email if provided
    if user_email:
        user = db.query(User).filter(User.email.ilike(f"%{user_email}%")).first()
        if user:
            query = query.filter(TenderMatch.user_id == user.id)

    total = query.count()

    matches = query.order_by(desc(TenderMatch.created_at))\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    results = []
    for match in matches:
        user = db.query(User).filter(User.id == match.user_id).first()
        tender = db.query(Tender).filter(Tender.id == match.tender_id).first()

        results.append({
            "id": match.id,
            "user_email": user.email if user else "Unknown",
            "user_name": user.full_name if user else None,
            "tender_title": tender.title if tender else "Unknown",
            "publication_number": tender.publication_number if tender else "Unknown",
            "match_score": match.match_score,
            "is_saved": match.is_saved,
            "is_dismissed": match.is_dismissed,
            "is_applied": match.is_applied,
            "created_at": match.created_at.isoformat() if match.created_at else None
        })

    return {
        "matches": results,
        "total": total,
        "page": page,
        "page_size": page_size
    }


# ============================================================================
# Profile Management
# ============================================================================

@router.get("/profiles")
async def list_all_profiles(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    active_only: bool = Query(False),
    search: Optional[str] = Query(None, description="Search by company name or user email"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    List all user tender profiles.
    """
    query = db.query(TenderProfile)

    if active_only:
        query = query.filter(TenderProfile.is_active == True)

    total = query.count()

    profiles = query.order_by(desc(TenderProfile.created_at))\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    results = []
    for profile in profiles:
        user = db.query(User).filter(User.id == profile.user_id).first()

        # Skip if search doesn't match
        if search:
            search_lower = search.lower()
            match = False
            if user and search_lower in user.email.lower():
                match = True
            if profile.company_name and search_lower in profile.company_name.lower():
                match = True
            if not match:
                continue

        match_count = db.query(TenderMatch).filter(
            TenderMatch.profile_id == profile.id
        ).count()

        results.append({
            "id": profile.id,
            "user_email": user.email if user else "Unknown",
            "user_name": user.full_name if user else None,
            "company_name": profile.company_name,
            "company_size": profile.company_size,
            "countries_count": len(profile.countries_of_interest) if profile.countries_of_interest else 0,
            "cpv_count": len(profile.cpv_codes or []) + len(profile.cpv_categories or []),
            "match_count": match_count,
            "is_active": profile.is_active,
            "created_at": profile.created_at.isoformat() if profile.created_at else None
        })

    return {
        "profiles": results,
        "total": total,
        "page": page,
        "page_size": page_size
    }


# ============================================================================
# Statistics & Settings
# ============================================================================

@router.get("/stats", response_model=AdminTenderStats)
async def get_admin_stats(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive admin statistics for Tenderator.
    """
    # Tender counts
    total_tenders = db.query(Tender).count()
    open_tenders = db.query(Tender).filter(Tender.status == "open").count()
    closed_tenders = db.query(Tender).filter(Tender.status == "closed").count()
    awarded_tenders = db.query(Tender).filter(Tender.status == "awarded").count()

    # Tenders this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    tenders_this_week = db.query(Tender).filter(
        Tender.created_at >= week_ago
    ).count()

    # By country
    country_counts = db.query(
        Tender.buyer_country,
        func.count(Tender.id)
    ).group_by(Tender.buyer_country).all()
    tenders_by_country = {c: count for c, count in country_counts if c}

    # By sector (CPV prefix)
    cpv_counts = db.query(
        func.substring(Tender.cpv_main, 1, 2),
        func.count(Tender.id)
    ).filter(Tender.cpv_main.isnot(None)).group_by(
        func.substring(Tender.cpv_main, 1, 2)
    ).all()
    tenders_by_sector = {cpv: count for cpv, count in cpv_counts if cpv}

    # Average value
    avg_value = db.query(func.avg(Tender.estimated_value)).filter(
        Tender.estimated_value.isnot(None)
    ).scalar()

    # Profile stats
    total_profiles = db.query(TenderProfile).count()
    active_profiles = db.query(TenderProfile).filter(
        TenderProfile.is_active == True
    ).count()

    # Match stats
    total_matches = db.query(TenderMatch).count()
    saved_matches = db.query(TenderMatch).filter(
        TenderMatch.is_saved == True
    ).count()

    # Fetch job stats
    fetch_jobs_count = db.query(TenderFetchJob).count()
    last_fetch = db.query(TenderFetchJob).order_by(
        desc(TenderFetchJob.completed_at)
    ).first()

    return AdminTenderStats(
        total_tenders=total_tenders,
        open_tenders=open_tenders,
        closed_tenders=closed_tenders,
        awarded_tenders=awarded_tenders,
        tenders_this_week=tenders_this_week,
        tenders_by_country=tenders_by_country,
        tenders_by_sector=tenders_by_sector,
        average_value=avg_value,
        total_profiles=total_profiles,
        active_profiles=active_profiles,
        total_matches=total_matches,
        saved_matches=saved_matches,
        fetch_jobs_count=fetch_jobs_count,
        last_fetch_at=last_fetch.completed_at if last_fetch else None
    )


@router.get("/settings")
async def get_settings(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get current Tenderator settings from database.
    """
    # Get or create settings (singleton pattern)
    settings = db.query(TenderatorSettingsModel).filter(
        TenderatorSettingsModel.id == 1
    ).first()

    if not settings:
        # Create default settings if none exist
        settings = TenderatorSettingsModel(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings.to_dict()


@router.put("/settings")
async def update_settings(
    settings_data: TenderatorSettings,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update Tenderator settings in database.
    """
    try:
        # Get or create settings
        settings = db.query(TenderatorSettingsModel).filter(
            TenderatorSettingsModel.id == 1
        ).first()

        if not settings:
            settings = TenderatorSettingsModel(id=1)
            db.add(settings)

        # Update fields from request
        update_data = settings_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        settings.updated_by = admin.id
        db.commit()
        db.refresh(settings)

        logger.info(f"Tenderator settings updated by admin {admin.id}")

        return {
            "message": "Settings updated successfully",
            "settings": settings.to_dict()
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )


# ============================================================================
# Export
# ============================================================================

@router.get("/export")
async def export_tenders(
    format: str = Query("csv", description="csv or json"),
    status_filter: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Export tenders data.
    """
    query = db.query(Tender)

    if status_filter:
        query = query.filter(Tender.status == status_filter)

    if country:
        query = query.filter(Tender.buyer_country == country.upper())

    tenders = query.all()

    if format == "json":
        return {
            "tenders": [t.to_dict() for t in tenders],
            "count": len(tenders),
            "exported_at": datetime.utcnow().isoformat()
        }

    # CSV format
    csv_rows = ["publication_number,title,country,status,value,deadline,sme_score,source"]
    for t in tenders:
        row = ",".join([
            t.publication_number or "",
            f'"{(t.title or "").replace(",", ";")[:100]}"',
            t.buyer_country or "",
            t.status or "",
            str(t.estimated_value or ""),
            t.submission_deadline.isoformat() if t.submission_deadline else "",
            str(t.sme_suitability_score or ""),
            t.source or ""
        ])
        csv_rows.append(row)

    return {
        "csv": "\n".join(csv_rows),
        "count": len(tenders),
        "exported_at": datetime.utcnow().isoformat()
    }
