"""
Resolution-to-Legislation Matcher - Phase 1.3

Links EP resolutions (INL, INI, RSP) to related legislative procedures.
Uses multiple matching strategies with confidence scoring.

Matching Methods (in order of confidence):
1. OEIL cross-references (confidence: 1.0)
2. Commission follow-up documents (confidence: 0.9)
3. Title similarity via semantic search (confidence: 0.5-0.8)
4. EuroVoc code matching (confidence: 0.3-0.5)
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.ep_resolutions import (
    EPResolution, ResolutionToLegislation, CommissionFollowup,
    ResolutionType, MatchMethod
)

logger = logging.getLogger(__name__)


# Procedure reference patterns
PROCEDURE_REF_PATTERN = re.compile(r"\d{4}/\d{4}\([A-Z]{3}\)")
COM_REF_PATTERN = re.compile(r"COM\(\d{4}\)\s*\d+")


@dataclass
class MatchResult:
    """Result of a resolution-to-legislation match."""
    resolution_id: str
    legislative_procedure_ref: str
    legislative_title: Optional[str]
    match_method: MatchMethod
    confidence: float
    match_details: Dict[str, Any]
    days_to_proposal: Optional[int] = None


class ResolutionLegislationMatcher:
    """
    Matches EP resolutions to related legislative procedures.

    Usage:
        matcher = ResolutionLegislationMatcher()
        matches = await matcher.find_legislation_for_resolution(resolution_id)
        await matcher.link_resolution_to_legislation(resolution_id, procedure_ref, method)
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._owns_db = db is None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def close(self):
        """Close database session if we own it."""
        if self._owns_db and self._db:
            self._db.close()
            self._db = None

    def extract_procedure_refs(self, text: str) -> List[str]:
        """Extract procedure references from text (e.g., 2024/0138(COD))."""
        if not text:
            return []
        return PROCEDURE_REF_PATTERN.findall(text)

    def extract_com_refs(self, text: str) -> List[str]:
        """Extract COM references from text (e.g., COM(2024) 123)."""
        if not text:
            return []
        return COM_REF_PATTERN.findall(text)

    def calculate_title_similarity(
        self,
        resolution_title: str,
        legislation_title: str
    ) -> float:
        """
        Calculate title similarity score (0.0 to 1.0).
        Uses simple word overlap for now; can be upgraded to semantic similarity.
        """
        if not resolution_title or not legislation_title:
            return 0.0

        # Normalize
        res_words = set(resolution_title.lower().split())
        leg_words = set(legislation_title.lower().split())

        # Remove common stop words
        stop_words = {"the", "a", "an", "of", "on", "in", "for", "to", "and", "or"}
        res_words -= stop_words
        leg_words -= stop_words

        if not res_words or not leg_words:
            return 0.0

        # Jaccard similarity
        intersection = res_words & leg_words
        union = res_words | leg_words

        return len(intersection) / len(union) if union else 0.0

    def calculate_eurovoc_overlap(
        self,
        resolution_codes: List[str],
        legislation_codes: List[str]
    ) -> float:
        """
        Calculate EuroVoc code overlap score (0.0 to 1.0).
        """
        if not resolution_codes or not legislation_codes:
            return 0.0

        res_set = set(resolution_codes)
        leg_set = set(legislation_codes)

        intersection = res_set & leg_set
        union = res_set | leg_set

        return len(intersection) / len(union) if union else 0.0

    async def find_oeil_crossrefs(
        self,
        resolution: EPResolution
    ) -> List[MatchResult]:
        """
        Find explicit OEIL cross-references for a resolution.
        These are the highest confidence matches.
        """
        matches = []

        # Check if resolution has related procedures in OEIL URL or text
        # This would typically involve fetching the OEIL page and parsing
        # For now, we check if there are procedure refs in the summary

        if resolution.summary:
            procedure_refs = self.extract_procedure_refs(resolution.summary)
            for ref in procedure_refs:
                # Only consider COD/CNS/APP procedures (legislative)
                if any(t in ref for t in ["COD", "CNS", "APP"]):
                    matches.append(MatchResult(
                        resolution_id=str(resolution.id),
                        legislative_procedure_ref=ref,
                        legislative_title=None,
                        match_method=MatchMethod.OEIL_CROSSREF,
                        confidence=1.0,
                        match_details={"source": "resolution_summary"}
                    ))

        return matches

    async def find_commission_followup_matches(
        self,
        resolution: EPResolution
    ) -> List[MatchResult]:
        """
        Find matches from Commission follow-up documents.
        """
        matches = []

        # Query existing followups
        followups = self.db.query(CommissionFollowup).filter(
            CommissionFollowup.resolution_id == resolution.id,
            CommissionFollowup.results_in_legislation == True
        ).all()

        for followup in followups:
            if followup.legislative_ref:
                matches.append(MatchResult(
                    resolution_id=str(resolution.id),
                    legislative_procedure_ref=followup.legislative_ref,
                    legislative_title=followup.title,
                    match_method=MatchMethod.COMMISSION_FOLLOWUP,
                    confidence=0.9,
                    match_details={
                        "com_reference": followup.com_reference,
                        "followup_date": str(followup.followup_date) if followup.followup_date else None
                    },
                    days_to_proposal=self._calculate_days_to_proposal(
                        resolution.adoption_date,
                        followup.followup_date
                    )
                ))

        return matches

    async def find_title_similarity_matches(
        self,
        resolution: EPResolution,
        min_similarity: float = 0.4
    ) -> List[MatchResult]:
        """
        Find matches based on title similarity.
        Searches legislative carriages for similar titles.
        """
        matches = []

        try:
            # Import here to avoid circular imports
            from models.legislative_train import LegislativeCarriage

            # Get recent legislative proposals (within 3 years after resolution)
            if resolution.adoption_date:
                start_date = resolution.adoption_date
                end_date = resolution.adoption_date + timedelta(days=365 * 3)

                carriages = self.db.query(LegislativeCarriage).filter(
                    LegislativeCarriage.created_at >= start_date,
                    LegislativeCarriage.created_at <= end_date
                ).limit(500).all()

                for carriage in carriages:
                    similarity = self.calculate_title_similarity(
                        resolution.title,
                        carriage.title
                    )

                    if similarity >= min_similarity:
                        # Scale confidence based on similarity
                        confidence = 0.5 + (similarity * 0.3)  # 0.5-0.8 range

                        matches.append(MatchResult(
                            resolution_id=str(resolution.id),
                            legislative_procedure_ref=carriage.oeil_procedure_ref or f"carriage:{carriage.id}",
                            legislative_title=carriage.title,
                            match_method=MatchMethod.TITLE_SIMILARITY,
                            confidence=confidence,
                            match_details={
                                "similarity_score": similarity,
                                "carriage_id": str(carriage.id)
                            },
                            days_to_proposal=self._calculate_days_to_proposal(
                                resolution.adoption_date,
                                carriage.created_at.date() if carriage.created_at else None
                            )
                        ))

        except ImportError:
            logger.warning("LegislativeCarriage model not available")

        # Sort by confidence
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches[:10]  # Top 10 matches

    async def find_eurovoc_matches(
        self,
        resolution: EPResolution,
        min_overlap: float = 0.3
    ) -> List[MatchResult]:
        """
        Find matches based on EuroVoc code overlap.
        Lower confidence than other methods.
        """
        matches = []

        if not resolution.eurovoc_codes:
            return matches

        try:
            from models.legislative_train import LegislativeCarriage

            # This would require EuroVoc codes on carriages
            # For now, return empty - to be implemented when EuroVoc tagging is added
            pass

        except ImportError:
            pass

        return matches

    async def find_all_matches(
        self,
        resolution: EPResolution,
        include_low_confidence: bool = False
    ) -> List[MatchResult]:
        """
        Find all matches using all available methods.
        Returns matches sorted by confidence.
        """
        all_matches = []

        # 1. OEIL cross-references (highest confidence)
        oeil_matches = await self.find_oeil_crossrefs(resolution)
        all_matches.extend(oeil_matches)

        # 2. Commission follow-up
        followup_matches = await self.find_commission_followup_matches(resolution)
        all_matches.extend(followup_matches)

        # 3. Title similarity
        title_matches = await self.find_title_similarity_matches(resolution)
        all_matches.extend(title_matches)

        # 4. EuroVoc matches (if enabled)
        if include_low_confidence:
            eurovoc_matches = await self.find_eurovoc_matches(resolution)
            all_matches.extend(eurovoc_matches)

        # Deduplicate by procedure reference, keeping highest confidence
        seen = {}
        for match in all_matches:
            key = match.legislative_procedure_ref
            if key not in seen or match.confidence > seen[key].confidence:
                seen[key] = match

        # Sort by confidence
        result = sorted(seen.values(), key=lambda m: m.confidence, reverse=True)

        return result

    def _calculate_days_to_proposal(
        self,
        resolution_date,
        proposal_date
    ) -> Optional[int]:
        """Calculate days between resolution and proposal."""
        if not resolution_date or not proposal_date:
            return None
        try:
            from datetime import date
            if isinstance(resolution_date, datetime):
                resolution_date = resolution_date.date()
            if isinstance(proposal_date, datetime):
                proposal_date = proposal_date.date()
            delta = proposal_date - resolution_date
            return delta.days if delta.days >= 0 else None
        except Exception:
            return None

    async def link_resolution_to_legislation(
        self,
        resolution_id: str,
        legislative_procedure_ref: str,
        match_method: MatchMethod,
        confidence: float = 1.0,
        match_details: Optional[Dict[str, Any]] = None,
        legislative_title: Optional[str] = None,
        days_to_proposal: Optional[int] = None
    ) -> ResolutionToLegislation:
        """
        Create or update a link between resolution and legislation.
        """
        # Check if link exists
        existing = self.db.query(ResolutionToLegislation).filter(
            ResolutionToLegislation.resolution_id == resolution_id,
            ResolutionToLegislation.legislative_procedure_ref == legislative_procedure_ref
        ).first()

        if existing:
            # Update if higher confidence
            if confidence > existing.confidence:
                existing.match_method = match_method
                existing.confidence = confidence
                existing.match_details = match_details
                existing.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            return existing

        # Create new link
        link = ResolutionToLegislation(
            resolution_id=resolution_id,
            legislative_procedure_ref=legislative_procedure_ref,
            legislative_title=legislative_title,
            match_method=match_method,
            confidence=confidence,
            match_details=match_details or {},
            days_to_proposal=days_to_proposal
        )

        self.db.add(link)
        self.db.commit()

        return link

    async def process_resolution(
        self,
        resolution: EPResolution,
        auto_link: bool = True,
        min_confidence: float = 0.5
    ) -> List[MatchResult]:
        """
        Process a resolution: find matches and optionally create links.

        Args:
            resolution: The resolution to process
            auto_link: Automatically create database links for matches
            min_confidence: Minimum confidence threshold for auto-linking

        Returns:
            List of match results
        """
        matches = await self.find_all_matches(resolution)

        if auto_link:
            for match in matches:
                if match.confidence >= min_confidence:
                    await self.link_resolution_to_legislation(
                        resolution_id=match.resolution_id,
                        legislative_procedure_ref=match.legislative_procedure_ref,
                        match_method=match.match_method,
                        confidence=match.confidence,
                        match_details=match.match_details,
                        legislative_title=match.legislative_title,
                        days_to_proposal=match.days_to_proposal
                    )

        return matches

    async def process_all_unlinked(
        self,
        limit: int = 100,
        min_confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        Process all resolutions without links.
        """
        # Find resolutions without links
        subquery = self.db.query(ResolutionToLegislation.resolution_id)
        unlinked = self.db.query(EPResolution).filter(
            ~EPResolution.id.in_(subquery)
        ).limit(limit).all()

        processed = 0
        total_matches = 0

        for resolution in unlinked:
            matches = await self.process_resolution(
                resolution,
                auto_link=True,
                min_confidence=min_confidence
            )
            processed += 1
            total_matches += len([m for m in matches if m.confidence >= min_confidence])

        return {
            "processed": processed,
            "matches_created": total_matches
        }


# Singleton instance
_matcher_instance: Optional[ResolutionLegislationMatcher] = None


@dataclass
class ResolutionIndicator:
    """Resolution data as a leading indicator for a legislative procedure."""
    resolution_id: str
    procedure_ref: str
    title: str
    resolution_type: str
    adoption_date: Optional[str]
    vote_for: int
    vote_against: int
    vote_abstention: int
    vote_total: int
    support_percentage: float
    lead_committee: Optional[str]
    rapporteur: Optional[str]
    match_method: str
    match_confidence: float
    days_before_legislation: Optional[int]
    oeil_url: Optional[str]


async def find_resolutions_for_legislation(
    procedure_ref: str,
    db: Optional[Session] = None
) -> List[ResolutionIndicator]:
    """
    Find all resolutions that are linked to a specific legislative procedure.
    This is the reverse lookup - used for resolution leading indicators.

    Args:
        procedure_ref: The legislative procedure reference (e.g., "2024/0138(COD)")
        db: Optional database session

    Returns:
        List of ResolutionIndicator objects with vote data
    """
    close_db = db is None
    if db is None:
        db = SessionLocal()

    try:
        # Query ResolutionToLegislation joined with EPResolution
        links = db.query(ResolutionToLegislation, EPResolution).join(
            EPResolution,
            ResolutionToLegislation.resolution_id == EPResolution.id
        ).filter(
            ResolutionToLegislation.legislative_procedure_ref == procedure_ref
        ).order_by(
            ResolutionToLegislation.confidence.desc()
        ).all()

        indicators = []
        for link, resolution in links:
            # Calculate support percentage
            support_pct = 0.0
            if resolution.vote_total and resolution.vote_total > 0:
                support_pct = round(resolution.vote_for / resolution.vote_total * 100, 1)

            indicators.append(ResolutionIndicator(
                resolution_id=str(resolution.id),
                procedure_ref=resolution.procedure_ref,
                title=resolution.title,
                resolution_type=resolution.resolution_type.value if resolution.resolution_type else "OTHER",
                adoption_date=str(resolution.adoption_date) if resolution.adoption_date else None,
                vote_for=resolution.vote_for or 0,
                vote_against=resolution.vote_against or 0,
                vote_abstention=resolution.vote_abstention or 0,
                vote_total=resolution.vote_total or 0,
                support_percentage=support_pct,
                lead_committee=resolution.lead_committee,
                rapporteur=resolution.rapporteur,
                match_method=link.match_method.value if link.match_method else "MANUAL",
                match_confidence=link.confidence or 0.0,
                days_before_legislation=link.days_to_proposal,
                oeil_url=resolution.oeil_url
            ))

        return indicators

    finally:
        if close_db:
            db.close()


async def find_related_resolutions_by_similarity(
    procedure_ref: str,
    procedure_title: str,
    db: Optional[Session] = None,
    min_similarity: float = 0.3
) -> List[ResolutionIndicator]:
    """
    Find resolutions related to a legislative procedure by title similarity.
    Used when no explicit links exist in the database.

    Args:
        procedure_ref: The legislative procedure reference
        procedure_title: The title of the legislative procedure
        db: Optional database session
        min_similarity: Minimum title similarity threshold

    Returns:
        List of ResolutionIndicator objects
    """
    close_db = db is None
    if db is None:
        db = SessionLocal()

    try:
        # Get resolutions from the past 5 years
        from datetime import timedelta
        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=365 * 5)

        resolutions = db.query(EPResolution).filter(
            EPResolution.adoption_date >= cutoff_date
        ).all()

        # Create a temporary matcher for similarity calculation
        matcher = ResolutionLegislationMatcher(db)

        indicators = []
        for resolution in resolutions:
            similarity = matcher.calculate_title_similarity(
                resolution.title,
                procedure_title
            )

            if similarity >= min_similarity:
                support_pct = 0.0
                if resolution.vote_total and resolution.vote_total > 0:
                    support_pct = round(resolution.vote_for / resolution.vote_total * 100, 1)

                indicators.append(ResolutionIndicator(
                    resolution_id=str(resolution.id),
                    procedure_ref=resolution.procedure_ref,
                    title=resolution.title,
                    resolution_type=resolution.resolution_type.value if resolution.resolution_type else "OTHER",
                    adoption_date=str(resolution.adoption_date) if resolution.adoption_date else None,
                    vote_for=resolution.vote_for or 0,
                    vote_against=resolution.vote_against or 0,
                    vote_abstention=resolution.vote_abstention or 0,
                    vote_total=resolution.vote_total or 0,
                    support_percentage=support_pct,
                    lead_committee=resolution.lead_committee,
                    rapporteur=resolution.rapporteur,
                    match_method="TITLE_SIMILARITY",
                    match_confidence=round(0.5 + similarity * 0.3, 2),  # 0.5-0.8 range
                    days_before_legislation=None,
                    oeil_url=resolution.oeil_url
                ))

        # Sort by confidence
        indicators.sort(key=lambda x: x.match_confidence, reverse=True)
        return indicators[:10]  # Top 10

    finally:
        if close_db:
            db.close()


def get_resolution_matcher() -> ResolutionLegislationMatcher:
    """Get or create the resolution matcher instance."""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = ResolutionLegislationMatcher()
    return _matcher_instance
