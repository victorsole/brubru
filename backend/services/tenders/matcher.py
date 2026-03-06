"""
Tender Matching Service

Matches EU tenders to user profiles based on multiple criteria.
Produces scored matches stored in the database for user review.

Usage:
    from services.tenders.matcher import TenderMatcher

    matcher = TenderMatcher(db)
    matches = await matcher.match_all_users()
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models.tender import Tender, TenderProfile, TenderMatch

logger = logging.getLogger(__name__)


class MatchWeight(Enum):
    """Configurable weights for match scoring criteria."""
    CPV_MATCH = 0.30          # Sector/CPV code overlap
    COUNTRY_MATCH = 0.20      # Geographic match
    VALUE_MATCH = 0.20        # Value range compatibility
    DEADLINE_MATCH = 0.10     # Deadline feasibility
    SME_SCORE = 0.10          # SME suitability score
    KEYWORD_MATCH = 0.05      # Keyword overlap
    PROCEDURE_MATCH = 0.05    # Procedure type preference


@dataclass
class MatchResult:
    """Result of matching a tender to a profile."""
    tender_id: int
    profile_id: int
    user_id: str
    total_score: float
    score_breakdown: Dict[str, float]
    match_details: str
    barriers: List[str]
    opportunities: List[str]


class TenderMatcher:
    """
    Service for matching tenders to user profiles.

    The matching algorithm considers:
    - CPV code overlap (sector alignment)
    - Geographic preferences
    - Value range compatibility
    - Deadline feasibility
    - SME suitability scores
    - Keyword matching
    - Procedure type preferences
    """

    def __init__(
        self,
        db: Session,
        score_threshold: float = 50.0,
        weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize the matcher.

        Args:
            db: SQLAlchemy database session
            score_threshold: Minimum score to create a match (0-100)
            weights: Custom weight configuration (optional)
        """
        self.db = db
        self.score_threshold = score_threshold

        # Default weights from enum, can be overridden
        self.weights = weights or {
            "cpv_match": MatchWeight.CPV_MATCH.value,
            "country_match": MatchWeight.COUNTRY_MATCH.value,
            "value_match": MatchWeight.VALUE_MATCH.value,
            "deadline_match": MatchWeight.DEADLINE_MATCH.value,
            "sme_score": MatchWeight.SME_SCORE.value,
            "keyword_match": MatchWeight.KEYWORD_MATCH.value,
            "procedure_match": MatchWeight.PROCEDURE_MATCH.value
        }

    async def match_all_users(
        self,
        tender_ids: Optional[List[int]] = None,
        profile_ids: Optional[List[int]] = None
    ) -> int:
        """
        Run matching for all active profiles against open tenders.

        Args:
            tender_ids: Optional list of specific tender IDs to match
            profile_ids: Optional list of specific profile IDs to match

        Returns:
            Number of new matches created
        """
        # Get active profiles
        profile_query = self.db.query(TenderProfile).filter(
            TenderProfile.is_active == True
        )
        if profile_ids:
            profile_query = profile_query.filter(TenderProfile.id.in_(profile_ids))
        profiles = profile_query.all()

        if not profiles:
            logger.info("No active profiles to match")
            return 0

        # Get open tenders with valid deadlines
        tender_query = self.db.query(Tender).filter(
            and_(
                Tender.status == "open",
                or_(
                    Tender.submission_deadline.is_(None),
                    Tender.submission_deadline > datetime.now(timezone.utc)
                )
            )
        )
        if tender_ids:
            tender_query = tender_query.filter(Tender.id.in_(tender_ids))
        tenders = tender_query.all()

        if not tenders:
            logger.info("No open tenders to match")
            return 0

        logger.info(f"Matching {len(tenders)} tenders against {len(profiles)} profiles")

        matches_created = 0

        for profile in profiles:
            for tender in tenders:
                # Skip if match already exists
                existing = self.db.query(TenderMatch).filter(
                    and_(
                        TenderMatch.profile_id == profile.id,
                        TenderMatch.tender_id == tender.id
                    )
                ).first()

                if existing:
                    continue

                # Calculate match
                result = self._calculate_match(tender, profile)

                if result.total_score >= self.score_threshold:
                    match = TenderMatch(
                        tender_id=result.tender_id,
                        profile_id=result.profile_id,
                        user_id=result.user_id,
                        match_score=result.total_score,
                        match_reasons=result.score_breakdown,
                        match_details=result.match_details,
                        created_at=datetime.now(timezone.utc)
                    )
                    self.db.add(match)
                    matches_created += 1

            # Update profile last_matched_at
            profile.last_matched_at = datetime.now(timezone.utc)

        self.db.commit()
        logger.info(f"Created {matches_created} new tender matches")

        return matches_created

    async def match_single_tender(self, tender_id: int) -> List[MatchResult]:
        """
        Match a single tender against all active profiles.

        Useful when a new tender is added.

        Args:
            tender_id: Tender ID to match

        Returns:
            List of match results
        """
        tender = self.db.query(Tender).filter(Tender.id == tender_id).first()
        if not tender:
            logger.warning(f"Tender {tender_id} not found")
            return []

        profiles = self.db.query(TenderProfile).filter(
            TenderProfile.is_active == True
        ).all()

        results = []
        for profile in profiles:
            result = self._calculate_match(tender, profile)
            if result.total_score >= self.score_threshold:
                results.append(result)

        return results

    async def match_single_profile(self, profile_id: int) -> List[MatchResult]:
        """
        Match a single profile against all open tenders.

        Useful when a user updates their profile.

        Args:
            profile_id: Profile ID to match

        Returns:
            List of match results
        """
        profile = self.db.query(TenderProfile).filter(
            TenderProfile.id == profile_id
        ).first()
        if not profile:
            logger.warning(f"Profile {profile_id} not found")
            return []

        tenders = self.db.query(Tender).filter(
            and_(
                Tender.status == "open",
                or_(
                    Tender.submission_deadline.is_(None),
                    Tender.submission_deadline > datetime.now(timezone.utc)
                )
            )
        ).all()

        results = []
        for tender in tenders:
            result = self._calculate_match(tender, profile)
            if result.total_score >= self.score_threshold:
                results.append(result)

        return results

    def _calculate_match(
        self,
        tender: Tender,
        profile: TenderProfile
    ) -> MatchResult:
        """
        Calculate match score between a tender and profile.

        Returns:
            MatchResult with scores and details
        """
        scores = {}
        barriers = []
        opportunities = []

        # HARD FILTER: If user selected specific countries, only show those
        # (regardless of eu_wide setting - specific selections take priority)
        if profile.countries_of_interest and tender.buyer_country:
            if tender.buyer_country not in profile.countries_of_interest:
                # Return zero-score result to exclude this tender
                return MatchResult(
                    tender_id=tender.id,
                    profile_id=profile.id,
                    user_id=str(profile.user_id),
                    total_score=0.0,
                    score_breakdown={},
                    match_details="Country not in preferred list",
                    barriers=["Country not in your selected countries"],
                    opportunities=[]
                )

        # 1. CPV Code Match (30%)
        scores["cpv_match"] = self._score_cpv_match(tender, profile)
        if scores["cpv_match"] >= 0.8:
            opportunities.append("Strong sector alignment with your business")
        elif scores["cpv_match"] < 0.3:
            barriers.append("Low sector match - different CPV codes")

        # 2. Country Match (20%)
        scores["country_match"] = self._score_country_match(tender, profile)
        if scores["country_match"] >= 0.8:
            opportunities.append(f"Located in your target country ({tender.buyer_country})")

        # 3. Value Match (20%)
        scores["value_match"] = self._score_value_match(tender, profile)
        if scores["value_match"] < 0.5:
            if tender.estimated_value and profile.max_tender_value:
                if tender.estimated_value > profile.max_tender_value:
                    barriers.append(f"Contract value (€{tender.estimated_value:,.0f}) exceeds your maximum (€{profile.max_tender_value:,.0f})")

        # 4. Deadline Match (10%)
        scores["deadline_match"] = self._score_deadline_match(tender, profile)
        if scores["deadline_match"] < 0.5:
            if tender.submission_deadline:
                days_left = (tender.submission_deadline - datetime.now(timezone.utc)).days
                barriers.append(f"Tight deadline - only {days_left} days remaining")
        elif scores["deadline_match"] >= 0.8:
            opportunities.append("Comfortable deadline for bid preparation")

        # 5. SME Score (10%)
        scores["sme_score"] = self._score_sme_suitability(tender, profile)
        if tender.sme_suitability_score and tender.sme_suitability_score >= 70:
            opportunities.append("High SME suitability score")
        elif tender.sme_suitability_score and tender.sme_suitability_score < 40:
            barriers.append("Low SME suitability - may favor larger companies")

        # 6. Keyword Match (5%)
        scores["keyword_match"] = self._score_keyword_match(tender, profile)
        if scores["keyword_match"] >= 0.5:
            opportunities.append("Keywords match your expertise areas")

        # 7. Procedure Match (5%)
        scores["procedure_match"] = self._score_procedure_match(tender, profile)
        if tender.procedure_type == "open":
            opportunities.append("Open procedure - accessible to all bidders")
        elif tender.procedure_type in ["restricted", "negotiated"]:
            barriers.append(f"{tender.procedure_type.capitalize()} procedure - may require pre-qualification")

        # Additional checks
        if tender.has_lots and tender.lot_count and tender.lot_count > 1:
            opportunities.append(f"Multiple lots ({tender.lot_count}) - partial bidding possible")

        if tender.is_framework:
            barriers.append("Framework agreement - typically favors established suppliers")

        if profile.exclude_frameworks and tender.is_framework:
            scores["procedure_match"] = 0  # Penalize frameworks if excluded

        # 8. DG GROW regulatory risk bonus/penalty (not weighted, direct adjustment)
        try:
            from services.tenders.dg_grow_enrichment import DGGrowEnrichment
            enrichment = DGGrowEnrichment(self.db)
            risk_data = enrichment.get_regulatory_risk_score(
                tender.cpv_main or "", tender.buyer_country
            )
            if risk_data.get("risk_level") == "high":
                barriers.append(f"High regulatory risk: {risk_data['tris_count']} active technical regulations, "
                                f"{risk_data['tbt_count']} trade barriers in this sector")
            elif risk_data.get("risk_level") == "low" and risk_data.get("score_adjustment", 0) > 0:
                opportunities.append("Stable regulatory environment in this sector")
        except Exception:
            risk_data = {"score_adjustment": 0}

        # Calculate weighted total
        total_score = sum(
            scores.get(key, 0) * self.weights.get(key, 0)
            for key in self.weights.keys()
        ) * 100  # Scale to 0-100

        # Apply DG GROW regulatory risk adjustment
        total_score += risk_data.get("score_adjustment", 0)
        total_score = max(0, min(100, total_score))  # Clamp to 0-100

        # Generate match details summary
        match_details = self._generate_match_details(
            tender, profile, scores, barriers, opportunities
        )

        return MatchResult(
            tender_id=tender.id,
            profile_id=profile.id,
            user_id=str(profile.user_id),
            total_score=round(total_score, 1),
            score_breakdown=scores,
            match_details=match_details,
            barriers=barriers,
            opportunities=opportunities
        )

    def _score_cpv_match(self, tender: Tender, profile: TenderProfile) -> float:
        """Score CPV code overlap (0-1)."""
        if not profile.cpv_codes and not profile.cpv_categories:
            return 0.5  # Neutral if no preferences

        # If tender has no CPV data, treat as neutral rather than penalizing
        if not tender.cpv_main and not tender.cpv_codes:
            return 0.5  # Unknown sector - neutral score

        score = 0.0

        # Exact CPV code match
        if tender.cpv_codes and profile.cpv_codes:
            matching = set(tender.cpv_codes) & set(profile.cpv_codes)
            if matching:
                score = max(score, len(matching) / len(profile.cpv_codes))

        # Category prefix match (e.g., "72" matches "72000000")
        if tender.cpv_main and profile.cpv_categories:
            for category in profile.cpv_categories:
                if tender.cpv_main.startswith(category):
                    score = max(score, 0.8)
                    break

        # Additional CPV codes from tender
        if tender.cpv_codes and profile.cpv_categories:
            for cpv in tender.cpv_codes:
                for category in profile.cpv_categories:
                    if cpv.startswith(category):
                        score = max(score, 0.7)
                        break

        return score

    def _score_country_match(self, tender: Tender, profile: TenderProfile) -> float:
        """Score geographic match (0-1)."""
        if not tender.buyer_country:
            return 0.5  # Unknown country

        # If specific countries are selected, those take priority
        if profile.countries_of_interest:
            if tender.buyer_country in profile.countries_of_interest:
                return 1.0  # Perfect match - in preferred countries
            elif profile.eu_wide:
                return 0.3  # EU-wide but not in preferred list - lower score
            else:
                return 0.0  # Not in target countries and not EU-wide - no match

        # No specific countries selected
        if profile.eu_wide:
            return 0.8  # Open to all EU

        return 0.5  # No preference specified

    def _score_value_match(self, tender: Tender, profile: TenderProfile) -> float:
        """Score value range compatibility (0-1)."""
        if tender.estimated_value is None:
            return 0.5  # Unknown value

        # Check minimum
        if profile.min_tender_value and tender.estimated_value < profile.min_tender_value:
            # Below minimum - lower score
            return 0.3

        # Check maximum
        if profile.max_tender_value and tender.estimated_value > profile.max_tender_value:
            # Above maximum - check how much over
            overage = tender.estimated_value / profile.max_tender_value
            if overage > 2:
                return 0.1  # Way over budget
            else:
                return 0.4  # Slightly over

        # Within range
        return 1.0

    def _score_deadline_match(self, tender: Tender, profile: TenderProfile) -> float:
        """Score deadline feasibility (0-1)."""
        if not tender.submission_deadline:
            return 0.5  # Unknown deadline

        days_until = (tender.submission_deadline - datetime.now(timezone.utc)).days
        min_days = profile.min_deadline_days or 30

        if days_until < 0:
            return 0.0  # Deadline passed

        if days_until < min_days / 2:
            return 0.2  # Very tight

        if days_until < min_days:
            return 0.5  # Below preference but possible

        if days_until > min_days * 2:
            return 1.0  # Comfortable margin

        # Proportional score
        return 0.5 + 0.5 * (days_until - min_days) / min_days

    def _score_sme_suitability(self, tender: Tender, profile: TenderProfile) -> float:
        """Score based on tender's SME suitability (0-1)."""
        if tender.sme_suitability_score is None:
            return 0.5  # Unknown

        # Normalize 0-100 score to 0-1
        return tender.sme_suitability_score / 100

    def _score_keyword_match(self, tender: Tender, profile: TenderProfile) -> float:
        """Score keyword overlap (0-1)."""
        if not profile.keywords:
            return 0.5  # No keywords specified

        if not tender.title and not tender.description:
            return 0.5

        text = f"{tender.title or ''} {tender.description or ''}".lower()

        # Check excluded keywords first
        if profile.excluded_keywords:
            for keyword in profile.excluded_keywords:
                if keyword.lower() in text:
                    return 0.0  # Excluded keyword found

        # Count matching keywords
        matches = 0
        for keyword in profile.keywords:
            if keyword.lower() in text:
                matches += 1

        if matches == 0:
            return 0.3  # No matches

        return min(1.0, 0.5 + (matches / len(profile.keywords)) * 0.5)

    def _score_procedure_match(self, tender: Tender, profile: TenderProfile) -> float:
        """Score procedure type preference (0-1)."""
        if not tender.procedure_type:
            return 0.5

        if not profile.preferred_procedures:
            # Default preferences for SMEs
            if tender.procedure_type == "open":
                return 0.9  # Open procedures are most accessible
            elif tender.procedure_type in ["restricted", "negotiated"]:
                return 0.5  # Less accessible
            else:
                return 0.6

        if tender.procedure_type in profile.preferred_procedures:
            return 1.0

        return 0.4

    def _generate_match_details(
        self,
        tender: Tender,
        profile: TenderProfile,
        scores: Dict[str, float],
        barriers: List[str],
        opportunities: List[str]
    ) -> str:
        """Generate human-readable match summary."""
        parts = []

        # Overall assessment
        avg_score = sum(scores.values()) / len(scores) * 100
        if avg_score >= 70:
            parts.append("Strong match for your profile.")
        elif avg_score >= 50:
            parts.append("Moderate match - review carefully.")
        else:
            parts.append("Limited match - some criteria not met.")

        # Key strengths
        if opportunities:
            parts.append(f"Strengths: {opportunities[0]}")

        # Key concerns
        if barriers:
            parts.append(f"Consider: {barriers[0]}")

        # Deadline info
        if tender.submission_deadline:
            days = (tender.submission_deadline - datetime.now(timezone.utc)).days
            parts.append(f"Deadline: {days} days remaining.")

        return " ".join(parts)

    def get_match_statistics(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get matching statistics.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            Statistics dictionary
        """
        query = self.db.query(TenderMatch)

        if user_id:
            query = query.filter(TenderMatch.user_id == user_id)

        matches = query.all()

        if not matches:
            return {
                "total_matches": 0,
                "average_score": 0,
                "saved_count": 0,
                "dismissed_count": 0,
                "applied_count": 0
            }

        scores = [m.match_score for m in matches]

        return {
            "total_matches": len(matches),
            "average_score": sum(scores) / len(scores),
            "high_score_count": len([s for s in scores if s >= 70]),
            "saved_count": len([m for m in matches if m.is_saved]),
            "dismissed_count": len([m for m in matches if m.is_dismissed]),
            "applied_count": len([m for m in matches if m.is_applied])
        }


# Convenience function
async def run_tender_matching(
    db: Session,
    tender_ids: Optional[List[int]] = None,
    profile_ids: Optional[List[int]] = None,
    score_threshold: float = 50.0
) -> int:
    """
    Run tender matching algorithm.

    Args:
        db: Database session
        tender_ids: Optional specific tenders to match
        profile_ids: Optional specific profiles to match
        score_threshold: Minimum match score (0-100)

    Returns:
        Number of matches created
    """
    matcher = TenderMatcher(db, score_threshold=score_threshold)
    return await matcher.match_all_users(tender_ids, profile_ids)
