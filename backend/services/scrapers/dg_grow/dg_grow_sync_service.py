"""
DG GROW Sync Service

Coordinates syncing data from all 4 DG GROW databases to PostgreSQL.
Orchestrates NANDO, TRIS, TBT, and EMI scrapers.

Usage:
    from services.scrapers.dg_grow.dg_grow_sync_service import DGGrowSyncService

    service = DGGrowSyncService(db)
    stats = await service.sync_all()
    stats = await service.sync_tris(days=7)
    stats = await service.sync_nando(country="BE")
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import and_

from models.dg_grow import (
    NotifiedBody,
    TechnicalRegulation,
    TradeBarrierNotification,
    IndustrialEcosystemData,
)
from services.scrapers.dg_grow.nando_scraper import NANDOScraper
from services.scrapers.dg_grow.tris_scraper import TRISScraper
from services.scrapers.dg_grow.tbt_scraper import TBTScraper
from services.scrapers.dg_grow.emi_scraper import EMIScraper, ECOSYSTEMS, INDICATORS

logger = logging.getLogger(__name__)


class DGGrowSyncService:
    """
    Sync coordinator for all DG GROW database scrapers.
    """

    def __init__(self, db: Session):
        self.db = db
        self.nando = NANDOScraper()
        self.tris = TRISScraper()
        self.tbt = TBTScraper()
        self.emi = EMIScraper()

    async def sync_all(self) -> Dict[str, Any]:
        """
        Sync all DG GROW databases.

        Returns:
            Stats dict with counts per source
        """
        stats = {
            "started_at": datetime.utcnow().isoformat(),
            "nando": {"synced": 0, "errors": 0},
            "tris": {"synced": 0, "errors": 0},
            "tbt": {"synced": 0, "errors": 0},
            "emi": {"synced": 0, "errors": 0},
        }

        # Sync each source, continue on errors
        try:
            nando_stats = await self.sync_nando()
            stats["nando"] = nando_stats
        except Exception as e:
            logger.error(f"NANDO sync failed: {e}")
            stats["nando"]["errors"] = 1

        try:
            tris_stats = await self.sync_tris()
            stats["tris"] = tris_stats
        except Exception as e:
            logger.error(f"TRIS sync failed: {e}")
            stats["tris"]["errors"] = 1

        try:
            tbt_stats = await self.sync_tbt()
            stats["tbt"] = tbt_stats
        except Exception as e:
            logger.error(f"TBT sync failed: {e}")
            stats["tbt"]["errors"] = 1

        try:
            emi_stats = await self.sync_emi()
            stats["emi"] = emi_stats
        except Exception as e:
            logger.error(f"EMI sync failed: {e}")
            stats["emi"]["errors"] = 1

        stats["completed_at"] = datetime.utcnow().isoformat()

        total = sum(s.get("synced", 0) for s in stats.values() if isinstance(s, dict))
        logger.info(f"[OK] DG GROW sync complete: {total} records synced")
        return stats

    async def sync_nando(self, country: Optional[str] = None) -> Dict[str, int]:
        """
        Sync notified bodies from NANDO/SMCS.

        Args:
            country: Optional country filter (ISO alpha-2)

        Returns:
            Stats dict
        """
        logger.info(f"[START] NANDO sync (country={country})")
        stats = {"synced": 0, "new": 0, "updated": 0, "errors": 0}

        bodies = await self.nando.search_notified_bodies(country=country, limit=200)

        for body_data in bodies:
            try:
                nando_id = body_data.get("nando_id")
                if not nando_id:
                    continue

                existing = self.db.query(NotifiedBody).filter(
                    NotifiedBody.nando_id == nando_id
                ).first()

                if existing:
                    # Update
                    for key, value in body_data.items():
                        if key != "raw_data" and hasattr(existing, key) and value:
                            setattr(existing, key, value)
                    existing.raw_data = body_data.get("raw_data")
                    stats["updated"] += 1
                else:
                    # Insert
                    new_body = NotifiedBody(
                        nando_id=nando_id,
                        body_name=body_data.get("body_name", ""),
                        body_number=body_data.get("body_number"),
                        country=body_data.get("country", ""),
                        address=body_data.get("address"),
                        city=body_data.get("city"),
                        postal_code=body_data.get("postal_code"),
                        phone=body_data.get("phone"),
                        email=body_data.get("email"),
                        website=body_data.get("website"),
                        directives=body_data.get("directives"),
                        directive_names=body_data.get("directive_names"),
                        product_areas=body_data.get("product_areas"),
                        cpv_mapping=body_data.get("cpv_mapping"),
                        status=body_data.get("status", "active"),
                        source_url=body_data.get("source_url"),
                        raw_data=body_data.get("raw_data"),
                    )
                    self.db.add(new_body)
                    stats["new"] += 1

                stats["synced"] += 1

            except Exception as e:
                logger.error(f"Failed to sync notified body {body_data.get('nando_id')}: {e}")
                stats["errors"] += 1

        self.db.commit()
        logger.info(f"[OK] NANDO sync: {stats['new']} new, {stats['updated']} updated, {stats['errors']} errors")
        return stats

    async def sync_tris(self, days: int = 7, country: Optional[str] = None) -> Dict[str, int]:
        """
        Sync TRIS technical regulation notifications.

        Args:
            days: Look back period (default: 7)
            country: Optional country filter

        Returns:
            Stats dict
        """
        logger.info(f"[START] TRIS sync (days={days}, country={country})")
        stats = {"synced": 0, "new": 0, "updated": 0, "errors": 0}

        if country:
            notifications = await self.tris.search_notifications(country=country)
        else:
            notifications = await self.tris.get_recent_notifications(days=days)

        for notif in notifications:
            try:
                number = notif.get("notification_number")
                if not number:
                    continue

                existing = self.db.query(TechnicalRegulation).filter(
                    TechnicalRegulation.notification_number == number
                ).first()

                # Parse dates
                notification_date = None
                standstill_end = None
                date_str = notif.get("notification_date")
                if date_str:
                    try:
                        notification_date = datetime.fromisoformat(date_str) if isinstance(date_str, str) else date_str
                    except (ValueError, TypeError):
                        pass
                standstill_str = notif.get("standstill_end_date")
                if standstill_str:
                    try:
                        standstill_end = datetime.fromisoformat(standstill_str) if isinstance(standstill_str, str) else standstill_str
                    except (ValueError, TypeError):
                        pass

                if existing:
                    existing.title = notif.get("title", existing.title)
                    existing.country = notif.get("country", existing.country)
                    existing.country_name = notif.get("country_name", existing.country_name)
                    if notification_date:
                        existing.notification_date = notification_date
                    if standstill_end:
                        existing.standstill_end_date = standstill_end
                    existing.cpv_mapping = notif.get("cpv_mapping", existing.cpv_mapping)
                    existing.status = notif.get("status", existing.status)
                    stats["updated"] += 1
                else:
                    new_reg = TechnicalRegulation(
                        notification_number=number,
                        reference=notif.get("reference"),
                        title=notif.get("title", ""),
                        description=notif.get("description"),
                        product_sector=notif.get("product_sector"),
                        country=notif.get("country", ""),
                        country_name=notif.get("country_name"),
                        notification_date=notification_date or datetime.utcnow(),
                        standstill_end_date=standstill_end,
                        status=notif.get("status", "notified"),
                        has_detailed_opinion=notif.get("has_detailed_opinion", False),
                        has_comments=notif.get("has_comments", False),
                        related_eu_legislation=notif.get("related_eu_legislation"),
                        cpv_mapping=notif.get("cpv_mapping"),
                        source_url=notif.get("source_url"),
                        raw_data=notif.get("raw_data"),
                    )
                    self.db.add(new_reg)
                    stats["new"] += 1

                stats["synced"] += 1

            except Exception as e:
                logger.error(f"Failed to sync TRIS notification {notif.get('notification_number')}: {e}")
                stats["errors"] += 1

        self.db.commit()
        logger.info(f"[OK] TRIS sync: {stats['new']} new, {stats['updated']} updated, {stats['errors']} errors")
        return stats

    async def sync_tbt(self, eu_only: bool = True) -> Dict[str, int]:
        """
        Sync TBT trade barrier notifications.

        Args:
            eu_only: Only sync EU-originated notifications (default: True)

        Returns:
            Stats dict
        """
        logger.info(f"[START] TBT sync (eu_only={eu_only})")
        stats = {"synced": 0, "new": 0, "updated": 0, "errors": 0}

        notifications = await self.tbt.get_latest_eu_notifications(limit=50)

        for notif in notifications:
            try:
                notif_id = notif.get("notification_id")
                if not notif_id:
                    continue

                existing = self.db.query(TradeBarrierNotification).filter(
                    TradeBarrierNotification.notification_id == notif_id
                ).first()

                notification_date = None
                date_str = notif.get("notification_date")
                if date_str:
                    try:
                        notification_date = datetime.fromisoformat(date_str) if isinstance(date_str, str) else date_str
                    except (ValueError, TypeError):
                        pass

                if existing:
                    existing.title = notif.get("title", existing.title)
                    existing.country = notif.get("country", existing.country)
                    existing.cpv_mapping = notif.get("cpv_mapping", existing.cpv_mapping)
                    existing.product_area = notif.get("product_area", existing.product_area)
                    stats["updated"] += 1
                else:
                    new_tbt = TradeBarrierNotification(
                        notification_id=notif_id,
                        symbol=notif.get("symbol"),
                        title=notif.get("title", ""),
                        description=notif.get("description"),
                        product_description=notif.get("product_description"),
                        objective=notif.get("objective"),
                        country=notif.get("country", ""),
                        country_code=notif.get("country_code"),
                        hs_codes=notif.get("hs_codes"),
                        ics_codes=notif.get("ics_codes"),
                        product_area=notif.get("product_area"),
                        notification_date=notification_date or datetime.utcnow(),
                        comment_deadline=None,
                        status=notif.get("status", "notified"),
                        is_eu_notification=notif.get("is_eu_notification", False),
                        cpv_mapping=notif.get("cpv_mapping"),
                        source_url=notif.get("source_url"),
                        raw_data=notif.get("raw_data"),
                    )
                    self.db.add(new_tbt)
                    stats["new"] += 1

                stats["synced"] += 1

            except Exception as e:
                logger.error(f"Failed to sync TBT notification {notif.get('notification_id')}: {e}")
                stats["errors"] += 1

        self.db.commit()
        logger.info(f"[OK] TBT sync: {stats['new']} new, {stats['updated']} updated, {stats['errors']} errors")
        return stats

    async def sync_emi(self) -> Dict[str, int]:
        """
        Sync EMI industrial ecosystem reference data.

        Since EMI doesn't have a public data API, this populates
        the reference data from our structured mappings and
        attempts to scrape available reports.

        Returns:
            Stats dict
        """
        logger.info("[START] EMI sync (reference data)")
        stats = {"synced": 0, "new": 0, "updated": 0, "errors": 0}

        # Populate reference data from structured mappings
        for ecosystem_name, ecosystem_data in ECOSYSTEMS.items():
            for indicator_key in ecosystem_data["indicators"]:
                indicator = INDICATORS.get(indicator_key, {})

                try:
                    existing = self.db.query(IndustrialEcosystemData).filter(
                        and_(
                            IndustrialEcosystemData.ecosystem == ecosystem_name,
                            IndustrialEcosystemData.indicator == indicator.get("name", indicator_key),
                            IndustrialEcosystemData.period == "reference",
                        )
                    ).first()

                    if not existing:
                        new_data = IndustrialEcosystemData(
                            ecosystem=ecosystem_name,
                            indicator=indicator.get("name", indicator_key),
                            period="reference",
                            unit=indicator.get("unit", ""),
                            dimension=indicator.get("dimension", ""),
                            sub_dimension=indicator.get("sub_dimension", ""),
                            cpv_categories=ecosystem_data["cpv"],
                            source_url=f"{self.emi.BASE_URL}/ecosystems",
                        )
                        self.db.add(new_data)
                        stats["new"] += 1

                    stats["synced"] += 1

                except Exception as e:
                    logger.error(f"Failed to sync EMI data for {ecosystem_name}/{indicator_key}: {e}")
                    stats["errors"] += 1

        self.db.commit()
        logger.info(f"[OK] EMI sync: {stats['new']} new reference records, {stats['errors']} errors")
        return stats

    def get_stats(self) -> Dict[str, Any]:
        """Get database counts for each DG GROW table."""
        return {
            "notified_bodies": self.db.query(NotifiedBody).count(),
            "technical_regulations": self.db.query(TechnicalRegulation).count(),
            "trade_barrier_notifications": self.db.query(TradeBarrierNotification).count(),
            "industrial_ecosystem_data": self.db.query(IndustrialEcosystemData).count(),
        }

    def get_notified_bodies_for_tender(self, cpv_code: str, country: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get notified bodies relevant to a tender's CPV code and country.
        Used by Tenderator Bid Checklist.

        Args:
            cpv_code: Tender's main CPV code
            country: Buyer country (optional, filters bodies in that country)

        Returns:
            List of relevant notified bodies
        """
        cpv_category = cpv_code[:2]

        query = self.db.query(NotifiedBody).filter(
            NotifiedBody.status == "active",
            NotifiedBody.cpv_mapping.any(cpv_category),
        )

        if country:
            query = query.filter(NotifiedBody.country == country)

        bodies = query.order_by(NotifiedBody.body_name).limit(20).all()
        return [b.to_summary_dict() for b in bodies]

    def get_regulatory_risks_for_tender(
        self,
        cpv_code: str,
        country: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get regulatory risk signals for a tender.
        Combines TRIS (national regulations) and TBT (trade barriers).
        Used by Tenderator for risk assessment.

        Args:
            cpv_code: Tender's main CPV code
            country: Buyer country

        Returns:
            Risk assessment dict
        """
        cpv_category = cpv_code[:2]
        risks = {
            "technical_regulations": [],
            "trade_barriers": [],
            "risk_level": "low",
        }

        # TRIS: national regulations affecting this sector
        tris_query = self.db.query(TechnicalRegulation).filter(
            TechnicalRegulation.cpv_mapping.any(cpv_category),
            TechnicalRegulation.status.in_(["notified", "standstill"]),
        )
        if country:
            tris_query = tris_query.filter(TechnicalRegulation.country == country)
        tris_results = tris_query.order_by(TechnicalRegulation.notification_date.desc()).limit(5).all()
        risks["technical_regulations"] = [r.to_dict() for r in tris_results]

        # TBT: trade barriers
        tbt_query = self.db.query(TradeBarrierNotification).filter(
            TradeBarrierNotification.cpv_mapping.any(cpv_category),
            TradeBarrierNotification.status == "notified",
        )
        tbt_results = tbt_query.order_by(TradeBarrierNotification.notification_date.desc()).limit(5).all()
        risks["trade_barriers"] = [r.to_dict() for r in tbt_results]

        # Assess risk level
        total_risks = len(risks["technical_regulations"]) + len(risks["trade_barriers"])
        if total_risks >= 5:
            risks["risk_level"] = "high"
        elif total_risks >= 2:
            risks["risk_level"] = "medium"

        return risks

    def get_ecosystem_context_for_tender(self, cpv_code: str) -> List[Dict[str, Any]]:
        """
        Get industrial ecosystem context for a tender's sector.
        Used by chatbot to provide sector intelligence.

        Args:
            cpv_code: Tender's CPV code

        Returns:
            List of ecosystem data points
        """
        return self.emi.get_ecosystems_for_cpv(cpv_code)
