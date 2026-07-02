"""
DG GROW Database API Endpoints

API for accessing DG GROW data: notified bodies (NANDO), technical regulations (TRIS),
trade barrier notifications (TBT), and industrial ecosystem data (EMI).

All data enriches the Tenderator module and AI chatbot.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.database import get_db
from api.auth import get_current_user
from models.dg_grow import (
    NotifiedBody,
    TechnicalRegulation,
    TradeBarrierNotification,
    IndustrialEcosystemData,
)
from services.scrapers.dg_grow.dg_grow_sync_service import DGGrowSyncService
from services.scrapers.dg_grow.emi_scraper import EMIScraper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dg-grow", tags=["DG GROW Databases"])


# --- Statistics ---

@router.get("/stats")
async def get_dg_grow_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get record counts for all DG GROW tables."""
    service = DGGrowSyncService(db)
    return service.get_stats()


# --- NANDO: Notified Bodies ---

@router.get("/notified-bodies")
async def list_notified_bodies(
    country: Optional[str] = Query(None, description="ISO alpha-2 country code"),
    directive: Optional[str] = Query(None, description="EU directive reference"),
    cpv: Optional[str] = Query(None, description="CPV code (first 2 digits for category)"),
    status: str = Query("active", description="Status filter"),
    page: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List notified bodies with filters."""
    query = db.query(NotifiedBody).filter(NotifiedBody.status == status)

    if country:
        query = query.filter(NotifiedBody.country == country.upper())
    if directive:
        query = query.filter(NotifiedBody.directives.any(directive))
    if cpv:
        cpv_cat = cpv[:2]
        query = query.filter(NotifiedBody.cpv_mapping.any(cpv_cat))

    total = query.count()
    bodies = query.order_by(NotifiedBody.body_name).offset(page * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "results": [b.to_dict() for b in bodies],
    }


@router.get("/notified-bodies/for-tender/{cpv_code}")
async def get_notified_bodies_for_tender(
    cpv_code: str,
    country: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get notified bodies relevant to a tender's CPV code. Used by Bid Checklist."""
    service = DGGrowSyncService(db)
    bodies = service.get_notified_bodies_for_tender(cpv_code, country)
    return {"cpv_code": cpv_code, "country": country, "bodies": bodies, "count": len(bodies)}


# --- TRIS: Technical Regulations ---

@router.get("/technical-regulations")
def list_technical_regulations(
    country: Optional[str] = Query(None, description="ISO alpha-2 country code"),
    sector: Optional[str] = Query(None, description="Product sector"),
    cpv: Optional[str] = Query(None, description="CPV code"),
    status: Optional[str] = Query(None),
    page: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List technical regulation notifications."""
    query = db.query(TechnicalRegulation)

    if country:
        query = query.filter(TechnicalRegulation.country == country.upper())
    if sector:
        query = query.filter(TechnicalRegulation.product_sector.ilike(f"%{sector}%"))
    if cpv:
        query = query.filter(TechnicalRegulation.cpv_mapping.any(cpv[:2]))
    if status:
        query = query.filter(TechnicalRegulation.status == status)

    total = query.count()
    regs = query.order_by(TechnicalRegulation.notification_date.desc()).offset(page * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "results": [r.to_dict() for r in regs],
    }


# --- TBT: Trade Barriers ---

@router.get("/trade-barriers")
def list_trade_barriers(
    country: Optional[str] = Query(None),
    product_area: Optional[str] = Query(None),
    cpv: Optional[str] = Query(None),
    eu_only: bool = Query(False),
    page: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List TBT trade barrier notifications."""
    query = db.query(TradeBarrierNotification)

    if country:
        query = query.filter(TradeBarrierNotification.country.ilike(f"%{country}%"))
    if product_area:
        query = query.filter(TradeBarrierNotification.product_area.ilike(f"%{product_area}%"))
    if cpv:
        query = query.filter(TradeBarrierNotification.cpv_mapping.any(cpv[:2]))
    if eu_only:
        query = query.filter(TradeBarrierNotification.is_eu_notification == True)

    total = query.count()
    notifs = query.order_by(TradeBarrierNotification.notification_date.desc()).offset(page * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "results": [n.to_dict() for n in notifs],
    }


# --- EMI: Industrial Ecosystems ---

@router.get("/ecosystems")
async def list_ecosystems(
    current_user=Depends(get_current_user),
):
    """List all 14 industrial ecosystems with CPV mappings."""
    emi = EMIScraper()
    return {"ecosystems": emi.get_all_ecosystems()}


@router.get("/ecosystems/for-cpv/{cpv_code}")
async def get_ecosystems_for_cpv(
    cpv_code: str,
    current_user=Depends(get_current_user),
):
    """Get industrial ecosystems relevant to a CPV code."""
    emi = EMIScraper()
    ecosystems = emi.get_ecosystems_for_cpv(cpv_code)
    return {"cpv_code": cpv_code, "ecosystems": ecosystems, "count": len(ecosystems)}


@router.get("/ecosystem-data")
def list_ecosystem_data(
    ecosystem: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    dimension: Optional[str] = Query(None),
    page: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List industrial ecosystem data points."""
    query = db.query(IndustrialEcosystemData)

    if ecosystem:
        query = query.filter(IndustrialEcosystemData.ecosystem.ilike(f"%{ecosystem}%"))
    if country:
        query = query.filter(IndustrialEcosystemData.country == country.upper())
    if dimension:
        query = query.filter(IndustrialEcosystemData.dimension == dimension)

    total = query.count()
    data = query.order_by(IndustrialEcosystemData.ecosystem).offset(page * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "results": [d.to_dict() for d in data],
    }


# --- Risk Assessment for Tenderator ---

@router.get("/regulatory-risks/{cpv_code}")
async def get_regulatory_risks(
    cpv_code: str,
    country: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get regulatory risk assessment for a tender sector.
    Combines TRIS technical regulations and TBT trade barriers.
    Used by Tenderator for risk signals.
    """
    service = DGGrowSyncService(db)
    risks = service.get_regulatory_risks_for_tender(cpv_code, country)
    return risks


# --- Sync (Admin/Blue tier only) ---

@router.post("/sync")
async def sync_dg_grow(
    source: Optional[str] = Query(None, description="nando, tris, tbt, emi, or all"),
    days: int = Query(7, description="Look back period for TRIS"),
    country: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Sync DG GROW databases (Blue tier / Admin only)."""
    if current_user.tier not in ("blue",):
        raise HTTPException(status_code=403, detail="Professional plan required")
    service = DGGrowSyncService(db)

    if source == "nando":
        stats = await service.sync_nando(country=country)
    elif source == "tris":
        stats = await service.sync_tris(days=days, country=country)
    elif source == "tbt":
        stats = await service.sync_tbt()
    elif source == "emi":
        stats = await service.sync_emi()
    else:
        stats = await service.sync_all()

    return {"source": source or "all", "stats": stats}
