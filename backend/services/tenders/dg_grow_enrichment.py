"""
DG GROW Enrichment for Tenderator

Integrates DG GROW databases (NANDO, TRIS, TBT, EMI) into the
Tenderator module's core workflows:

1. Matcher: Adds regulatory risk signals to match scoring
2. Bid Checklist: Enriches ESPD checklist with notified bodies
3. Chat Context: Provides sector intelligence for AI responses
4. Notifications: Alerts users about regulatory changes in their sectors

Usage:
    from services.tenders.dg_grow_enrichment import DGGrowEnrichment

    enrichment = DGGrowEnrichment(db)

    # Enrich a tender match with regulatory context
    risk_context = enrichment.get_tender_risk_context(tender)

    # Get notified bodies for bid checklist
    bodies = enrichment.get_notified_bodies_for_checklist(tender)

    # Get sector intelligence for chat
    sector_intel = enrichment.get_sector_intelligence(cpv_code)
"""

import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from models.dg_grow import (
    NotifiedBody,
    TechnicalRegulation,
    TradeBarrierNotification,
    IndustrialEcosystemData,
)
from services.scrapers.dg_grow.emi_scraper import ECOSYSTEMS, INDICATORS

logger = logging.getLogger(__name__)


class DGGrowEnrichment:
    """
    DG GROW data enrichment for Tenderator.

    Provides methods that integrate into existing Tenderator workflows
    without modifying the core matcher algorithm.
    """

    def __init__(self, db: Session):
        self.db = db

    # --- Matcher Integration ---

    def get_regulatory_risk_score(self, cpv_code: str, country: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate regulatory risk score for a tender's sector and country.
        Can be used as a bonus/penalty signal in the matcher.

        Args:
            cpv_code: Tender's main CPV code
            country: Buyer country code

        Returns:
            Risk assessment with score adjustment
        """
        cpv_category = cpv_code[:2] if cpv_code else ""
        if not cpv_category:
            return {"risk_level": "unknown", "score_adjustment": 0, "details": []}

        details = []

        # Count active TRIS regulations in this sector/country
        tris_query = self.db.query(TechnicalRegulation).filter(
            TechnicalRegulation.cpv_mapping.any(cpv_category),
            TechnicalRegulation.status.in_(["notified", "standstill"]),
        )
        if country:
            tris_query = tris_query.filter(TechnicalRegulation.country == country)
        tris_count = tris_query.count()

        if tris_count > 0:
            recent_regs = tris_query.order_by(desc(TechnicalRegulation.notification_date)).limit(3).all()
            for reg in recent_regs:
                details.append({
                    "type": "technical_regulation",
                    "source": "TRIS",
                    "title": reg.title[:100] if reg.title else "",
                    "country": reg.country,
                    "status": reg.status,
                    "url": reg.source_url,
                })

        # Count active TBT barriers
        tbt_query = self.db.query(TradeBarrierNotification).filter(
            TradeBarrierNotification.cpv_mapping.any(cpv_category),
            TradeBarrierNotification.status == "notified",
        )
        tbt_count = tbt_query.count()

        if tbt_count > 0:
            recent_tbt = tbt_query.order_by(desc(TradeBarrierNotification.notification_date)).limit(3).all()
            for tbt in recent_tbt:
                details.append({
                    "type": "trade_barrier",
                    "source": "TBT",
                    "title": tbt.title[:100] if tbt.title else "",
                    "country": tbt.country,
                    "url": tbt.source_url,
                })

        # Calculate risk level and score adjustment
        total_risks = tris_count + tbt_count
        if total_risks >= 5:
            risk_level = "high"
            score_adjustment = -5  # Slight penalty for high-risk sectors
        elif total_risks >= 2:
            risk_level = "medium"
            score_adjustment = 0  # Neutral
        else:
            risk_level = "low"
            score_adjustment = 2  # Slight bonus for stable regulatory environment

        return {
            "risk_level": risk_level,
            "score_adjustment": score_adjustment,
            "tris_count": tris_count,
            "tbt_count": tbt_count,
            "details": details,
        }

    # --- Bid Checklist Integration ---

    def get_notified_bodies_for_checklist(
        self,
        cpv_code: str,
        country: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get notified bodies relevant to a tender for the Bid Checklist.
        Tells bidders which conformity assessment bodies they may need.

        Args:
            cpv_code: Tender's main CPV code
            country: Buyer country (filters to bodies in that country)

        Returns:
            Dict with notified bodies and applicable directives
        """
        cpv_category = cpv_code[:2] if cpv_code else ""
        if not cpv_category:
            return {"bodies": [], "directives": [], "requires_conformity": False}

        query = self.db.query(NotifiedBody).filter(
            NotifiedBody.status == "active",
            NotifiedBody.cpv_mapping.any(cpv_category),
        )

        if country:
            query = query.filter(NotifiedBody.country == country)

        bodies = query.order_by(NotifiedBody.body_name).limit(15).all()

        if not bodies:
            return {"bodies": [], "directives": [], "requires_conformity": False}

        # Collect unique directives
        all_directives = set()
        for body in bodies:
            if body.directives:
                all_directives.update(body.directives)

        return {
            "requires_conformity": True,
            "body_count": len(bodies),
            "bodies": [
                {
                    "body_number": b.body_number,
                    "body_name": b.body_name,
                    "country": b.country,
                    "directives": b.directives or [],
                    "contact": {
                        "email": b.email,
                        "phone": b.phone,
                        "website": b.website,
                    },
                }
                for b in bodies
            ],
            "applicable_directives": list(all_directives),
            "note": (
                f"This tender's sector (CPV {cpv_category}xx) may require conformity "
                f"assessment by a notified body under {len(all_directives)} EU directive(s). "
                f"Found {len(bodies)} active notified bodies"
                + (f" in {country}" if country else " across the EU")
                + "."
            ),
        }

    def get_regulatory_alerts_for_checklist(
        self,
        cpv_code: str,
        country: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get active regulatory alerts relevant to a tender.
        Warns bidders about upcoming regulation changes.

        Args:
            cpv_code: Tender's CPV code
            country: Buyer country

        Returns:
            List of regulatory alerts
        """
        cpv_category = cpv_code[:2] if cpv_code else ""
        if not cpv_category:
            return []

        alerts = []

        # TRIS: regulations in standstill (may change requirements)
        tris_query = self.db.query(TechnicalRegulation).filter(
            TechnicalRegulation.cpv_mapping.any(cpv_category),
            TechnicalRegulation.status.in_(["notified", "standstill"]),
        )
        if country:
            tris_query = tris_query.filter(TechnicalRegulation.country == country)

        for reg in tris_query.order_by(desc(TechnicalRegulation.notification_date)).limit(5).all():
            alerts.append({
                "type": "TRIS",
                "severity": "warning" if reg.status == "standstill" else "info",
                "title": f"Draft technical regulation: {reg.title[:80]}" if reg.title else "Draft regulation",
                "country": reg.country,
                "status": reg.status,
                "standstill_end": reg.standstill_end_date.isoformat() if reg.standstill_end_date else None,
                "impact": "May change product requirements or conformity assessment procedures",
                "url": reg.source_url,
            })

        # TBT: trade barriers that could affect cross-border bidding
        tbt_query = self.db.query(TradeBarrierNotification).filter(
            TradeBarrierNotification.cpv_mapping.any(cpv_category),
            TradeBarrierNotification.status == "notified",
        )
        for tbt in tbt_query.order_by(desc(TradeBarrierNotification.notification_date)).limit(3).all():
            alerts.append({
                "type": "TBT",
                "severity": "info",
                "title": f"Trade barrier: {tbt.title[:80]}" if tbt.title else "Trade barrier notification",
                "country": tbt.country,
                "product_area": tbt.product_area,
                "impact": "May affect cross-border procurement or market access requirements",
                "url": tbt.source_url,
            })

        return alerts

    # --- Chat Context Integration ---

    def get_sector_intelligence(self, cpv_code: str) -> Dict[str, Any]:
        """
        Get comprehensive sector intelligence for AI chat context.
        Combines all DG GROW data for a given sector.

        Args:
            cpv_code: CPV code to look up

        Returns:
            Sector intelligence dict for AI context injection
        """
        cpv_category = cpv_code[:2] if cpv_code else ""
        if not cpv_category:
            return {}

        intel = {
            "cpv_category": cpv_category,
            "ecosystems": [],
            "notified_bodies_count": 0,
            "active_regulations": 0,
            "trade_barriers": 0,
            "risk_level": "low",
        }

        # Industrial ecosystems for this sector
        for name, data in ECOSYSTEMS.items():
            if cpv_category in data["cpv"]:
                intel["ecosystems"].append({
                    "name": name,
                    "indicators": [
                        INDICATORS.get(i, {"name": i}).get("name", i)
                        for i in data["indicators"]
                    ],
                })

        # Count notified bodies
        intel["notified_bodies_count"] = self.db.query(NotifiedBody).filter(
            NotifiedBody.status == "active",
            NotifiedBody.cpv_mapping.any(cpv_category),
        ).count()

        # Count active regulations
        intel["active_regulations"] = self.db.query(TechnicalRegulation).filter(
            TechnicalRegulation.cpv_mapping.any(cpv_category),
            TechnicalRegulation.status.in_(["notified", "standstill"]),
        ).count()

        # Count trade barriers
        intel["trade_barriers"] = self.db.query(TradeBarrierNotification).filter(
            TradeBarrierNotification.cpv_mapping.any(cpv_category),
            TradeBarrierNotification.status == "notified",
        ).count()

        # Overall risk level
        total = intel["active_regulations"] + intel["trade_barriers"]
        if total >= 5:
            intel["risk_level"] = "high"
        elif total >= 2:
            intel["risk_level"] = "medium"

        return intel

    def format_sector_context_for_ai(self, cpv_code: str) -> str:
        """
        Format sector intelligence as text block for AI context injection.

        Args:
            cpv_code: CPV code

        Returns:
            Formatted text block for system prompt
        """
        intel = self.get_sector_intelligence(cpv_code)
        if not intel or not intel.get("cpv_category"):
            return ""

        lines = [f"\n--- DG GROW SECTOR INTELLIGENCE (CPV {intel['cpv_category']}xx) ---"]

        if intel["ecosystems"]:
            eco_names = [e["name"] for e in intel["ecosystems"]]
            lines.append(f"Industrial ecosystems: {', '.join(eco_names)}")

        if intel["notified_bodies_count"]:
            lines.append(f"Active notified bodies: {intel['notified_bodies_count']} "
                         f"(conformity assessment may be required)")

        if intel["active_regulations"]:
            lines.append(f"Active technical regulation notifications (TRIS): {intel['active_regulations']} "
                         f"(draft national regulations in standstill)")

        if intel["trade_barriers"]:
            lines.append(f"Active trade barrier notifications (TBT): {intel['trade_barriers']}")

        lines.append(f"Regulatory risk level: {intel['risk_level'].upper()}")
        lines.append("--- END DG GROW CONTEXT ---")

        return "\n".join(lines)
