"""
SME Suitability Scoring Service

Analyzes EU procurement tenders and scores them for SME accessibility.
Uses multiple criteria to determine how suitable a tender is for small
and medium-sized enterprises.

Scoring Criteria:
- Contract value (smaller = more accessible)
- Procedure type (open procedures preferred)
- Time until deadline (more time = better)
- Lot structure (multiple lots increase chances)
- Requirements complexity
- Geographic proximity
- Framework exclusion

Score Range: 0-100 (higher = more SME-friendly)
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SMECategory(Enum):
    """SME size categories per EU definition"""
    MICRO = "micro"      # < 10 employees, < €2M turnover
    SMALL = "small"      # < 50 employees, < €10M turnover
    MEDIUM = "medium"    # < 250 employees, < €50M turnover


@dataclass
class SMEProfile:
    """SME company profile for scoring context"""
    size: SMECategory = SMECategory.SMALL
    annual_turnover: Optional[float] = None  # EUR
    employee_count: Optional[int] = None
    years_in_business: Optional[int] = None
    past_contract_value: Optional[float] = None  # Largest previous contract


@dataclass
class SMEScoreResult:
    """Result of SME suitability scoring"""
    overall_score: float
    category_scores: Dict[str, float]
    recommendations: List[str]
    risk_factors: List[str]
    confidence: float  # How confident we are in this score


class SMEScorer:
    """
    Scores tenders for SME suitability.

    The scoring algorithm considers:
    1. Financial accessibility (value, turnover requirements)
    2. Procedural accessibility (procedure type, deadlines)
    3. Competition level (lot structure, framework)
    4. Administrative burden (requirements complexity)

    Usage:
        scorer = SMEScorer()
        result = scorer.score_tender(tender_data, sme_profile)
        print(f"SME Score: {result.overall_score}/100")
    """

    # Value thresholds for SME categories (EUR)
    VALUE_THRESHOLDS = {
        SMECategory.MICRO: 500_000,
        SMECategory.SMALL: 2_000_000,
        SMECategory.MEDIUM: 10_000_000
    }

    # Weights for different scoring categories
    CATEGORY_WEIGHTS = {
        "value": 0.30,
        "procedure": 0.20,
        "deadline": 0.15,
        "lots": 0.10,
        "requirements": 0.15,
        "framework": 0.10
    }

    # Procedure type scores (1 = most SME-friendly)
    PROCEDURE_SCORES = {
        "open": 1.0,
        "restricted": 0.7,
        "neg-w-call": 0.5,
        "comp-dial": 0.4,
        "innovation": 0.6,
        "neg-wo-call": 0.2
    }

    def __init__(self):
        """Initialize the SME scorer"""
        self.default_profile = SMEProfile()

    def score_tender(
        self,
        tender_data: Dict[str, Any],
        sme_profile: Optional[SMEProfile] = None
    ) -> SMEScoreResult:
        """
        Score a tender for SME suitability.

        Args:
            tender_data: Tender information (from parser or database)
            sme_profile: Optional SME profile for personalized scoring

        Returns:
            SMEScoreResult with overall score, breakdown, and recommendations
        """
        profile = sme_profile or self.default_profile
        category_scores = {}
        recommendations = []
        risk_factors = []

        # Score each category
        category_scores["value"], value_rec, value_risk = self._score_value(
            tender_data, profile
        )

        category_scores["procedure"], proc_rec, proc_risk = self._score_procedure(
            tender_data
        )

        category_scores["deadline"], deadline_rec, deadline_risk = self._score_deadline(
            tender_data
        )

        category_scores["lots"], lots_rec, lots_risk = self._score_lots(
            tender_data
        )

        category_scores["requirements"], req_rec, req_risk = self._score_requirements(
            tender_data, profile
        )

        category_scores["framework"], fw_rec, fw_risk = self._score_framework(
            tender_data
        )

        # Collect recommendations and risks
        recommendations.extend([r for r in [value_rec, proc_rec, deadline_rec, lots_rec, req_rec, fw_rec] if r])
        risk_factors.extend([r for r in [value_risk, proc_risk, deadline_risk, lots_risk, req_risk, fw_risk] if r])

        # Calculate weighted average
        overall_score = sum(
            category_scores[cat] * weight
            for cat, weight in self.CATEGORY_WEIGHTS.items()
        ) * 100  # Scale to 0-100

        # Calculate confidence based on data completeness
        confidence = self._calculate_confidence(tender_data)

        return SMEScoreResult(
            overall_score=round(overall_score, 1),
            category_scores={k: round(v * 100, 1) for k, v in category_scores.items()},
            recommendations=recommendations,
            risk_factors=risk_factors,
            confidence=round(confidence, 2)
        )

    def _score_value(
        self,
        tender_data: Dict[str, Any],
        profile: SMEProfile
    ) -> Tuple[float, Optional[str], Optional[str]]:
        """Score based on contract value"""
        value = tender_data.get("estimated_value")
        recommendation = None
        risk = None

        if value is None:
            # Unknown value - moderate score
            return 0.5, None, "Contract value not specified"

        # Get threshold for SME category
        threshold = self.VALUE_THRESHOLDS.get(profile.size, 2_000_000)

        if value <= threshold * 0.2:
            # Very small contract - ideal for SMEs
            score = 1.0
            recommendation = "Contract value is very accessible for SMEs"
        elif value <= threshold * 0.5:
            # Small contract - good for SMEs
            score = 0.9
        elif value <= threshold:
            # Within SME range
            score = 0.7
            recommendation = "Contract is within typical SME range"
        elif value <= threshold * 2:
            # Stretching SME capacity
            score = 0.4
            risk = "Contract value may stretch SME financial capacity"
        else:
            # Too large for typical SMEs
            score = 0.2
            risk = "Contract value likely too large for SME without consortium"

        # Adjust for past contract experience
        if profile.past_contract_value:
            if value <= profile.past_contract_value * 1.5:
                score = min(1.0, score + 0.1)
            elif value > profile.past_contract_value * 3:
                score = max(0.1, score - 0.1)
                risk = "Contract significantly larger than previous experience"

        return score, recommendation, risk

    def _score_procedure(
        self,
        tender_data: Dict[str, Any]
    ) -> Tuple[float, Optional[str], Optional[str]]:
        """Score based on procedure type"""
        procedure = (tender_data.get("procedure_type") or "").lower()
        recommendation = None
        risk = None

        score = self.PROCEDURE_SCORES.get(procedure, 0.5)

        if procedure == "open":
            recommendation = "Open procedure - all companies can participate"
        elif procedure == "restricted":
            risk = "Restricted procedure - pre-qualification required"
        elif procedure in ["neg-w-call", "neg-wo-call"]:
            risk = "Negotiated procedure - may favor established suppliers"
        elif procedure == "comp-dial":
            risk = "Competitive dialogue - complex and resource-intensive"

        return score, recommendation, risk

    def _score_deadline(
        self,
        tender_data: Dict[str, Any]
    ) -> Tuple[float, Optional[str], Optional[str]]:
        """Score based on submission deadline"""
        deadline = tender_data.get("submission_deadline")
        recommendation = None
        risk = None

        if not deadline:
            return 0.5, None, "Submission deadline not specified"

        # Handle string dates
        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            except ValueError:
                return 0.5, None, "Invalid deadline format"

        # A deadline can arrive either tz-aware (read back from the TIMESTAMPTZ
        # column, or parsed from eForms, which carries an offset) or tz-naive
        # (built with datetime.now(), or any caller that did not think about
        # it). Subtracting the two raises TypeError and takes the whole score
        # down. Treat a naive deadline as UTC, which is what every other naive
        # datetime in this codebase means.
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        days_until = (deadline - datetime.now(timezone.utc)).days

        if days_until < 0:
            score = 0.0
            risk = "Deadline has passed"
        elif days_until < 14:
            score = 0.2
            risk = "Very tight deadline - less than 2 weeks"
        elif days_until < 30:
            score = 0.5
            risk = "Limited time - less than 1 month"
        elif days_until < 45:
            score = 0.7
            recommendation = "Adequate time for bid preparation"
        elif days_until < 60:
            score = 0.9
            recommendation = "Good timeline for thorough bid preparation"
        else:
            score = 1.0
            recommendation = "Excellent timeline - ample preparation time"

        return score, recommendation, risk

    def _score_lots(
        self,
        tender_data: Dict[str, Any]
    ) -> Tuple[float, Optional[str], Optional[str]]:
        """Score based on lot structure"""
        has_lots = tender_data.get("has_lots", False)
        lot_count = tender_data.get("lot_count") or 0
        recommendation = None
        risk = None

        if has_lots and lot_count > 1:
            if lot_count >= 5:
                score = 1.0
                recommendation = f"Multiple lots ({lot_count}) - SMEs can target specific parts"
            elif lot_count >= 3:
                score = 0.9
                recommendation = f"Divided into {lot_count} lots - increased SME accessibility"
            else:
                score = 0.7
                recommendation = f"Divided into {lot_count} lots"
        else:
            score = 0.5
            if (tender_data.get("estimated_value") or 0) > 1_000_000:
                risk = "Single lot for large contract may exclude SMEs"

        return score, recommendation, risk

    def _score_requirements(
        self,
        tender_data: Dict[str, Any],
        profile: SMEProfile
    ) -> Tuple[float, Optional[str], Optional[str]]:
        """Score based on qualification requirements"""
        score = 0.7  # Default neutral score
        recommendation = None
        risk = None

        # Check minimum requirements
        min_requirements = tender_data.get("minimum_requirements") or {}
        selection_criteria = tender_data.get("selection_criteria") or []

        # Turnover requirements
        min_turnover = min_requirements.get("minimum_turnover")
        if min_turnover and profile.annual_turnover:
            if min_turnover > profile.annual_turnover:
                score = 0.2
                risk = f"Turnover requirement (€{min_turnover:,.0f}) exceeds company turnover"
            elif min_turnover > profile.annual_turnover * 0.5:
                score = 0.5
                risk = "Turnover requirement is significant portion of company turnover"
            else:
                score = 0.8
                recommendation = "Turnover requirements within company capacity"

        # Experience requirements (count of criteria as proxy for complexity)
        if selection_criteria:
            criteria_count = len(selection_criteria)
            if criteria_count > 10:
                score = min(score, 0.4)
                risk = "Complex selection criteria may burden SME resources"
            elif criteria_count > 5:
                score = min(score, 0.6)

        # Check for specific SME-unfriendly indicators
        tech_ability = min_requirements.get("technical_ability")
        if tech_ability and isinstance(tech_ability, str):
            tech_req = tech_ability.lower()
            if any(term in tech_req for term in ["iso 9001", "iso 27001", "certification"]):
                score = min(score, 0.5)
                risk = "Certification requirements may be challenging for SMEs"

        return score, recommendation, risk

    def _score_framework(
        self,
        tender_data: Dict[str, Any]
    ) -> Tuple[float, Optional[str], Optional[str]]:
        """Score based on framework agreement status"""
        is_framework = tender_data.get("is_framework", False)
        is_joint = tender_data.get("is_joint_procurement", False)
        recommendation = None
        risk = None

        if is_framework:
            score = 0.4
            risk = "Framework agreement - typically favors larger suppliers"
        elif is_joint:
            score = 0.5
            risk = "Joint procurement - may have high volume requirements"
        else:
            score = 0.8
            recommendation = "Standard contract - no framework restrictions"

        return score, recommendation, risk

    def _calculate_confidence(self, tender_data: Dict[str, Any]) -> float:
        """
        Calculate confidence in the score based on data completeness.

        Returns value between 0 and 1.
        """
        key_fields = [
            "estimated_value",
            "procedure_type",
            "submission_deadline",
            "has_lots",
            "cpv_codes",
            "buyer_country"
        ]

        present_fields = sum(1 for f in key_fields if tender_data.get(f) is not None)
        base_confidence = present_fields / len(key_fields)

        # Bonus for having detailed requirements info
        if tender_data.get("selection_criteria"):
            base_confidence = min(1.0, base_confidence + 0.1)
        if tender_data.get("minimum_requirements"):
            base_confidence = min(1.0, base_confidence + 0.1)

        return base_confidence

    def get_sme_analysis(
        self,
        tender_data: Dict[str, Any],
        sme_profile: Optional[SMEProfile] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive SME analysis for a tender.

        Returns structured analysis suitable for storage in database.

        Args:
            tender_data: Tender information
            sme_profile: Optional SME profile

        Returns:
            Dictionary with score and analysis details
        """
        result = self.score_tender(tender_data, sme_profile)

        return {
            "sme_suitability_score": result.overall_score,
            "score_breakdown": result.category_scores,
            "recommendations": result.recommendations,
            "risk_factors": result.risk_factors,
            "confidence": result.confidence,
            "scoring_version": "1.0",
            "scored_at": datetime.utcnow().isoformat()
        }

    def batch_score_tenders(
        self,
        tenders: List[Dict[str, Any]],
        sme_profile: Optional[SMEProfile] = None
    ) -> List[Dict[str, Any]]:
        """
        Score multiple tenders and return sorted by SME suitability.

        Args:
            tenders: List of tender data dictionaries
            sme_profile: Optional SME profile for personalized scoring

        Returns:
            List of tenders with scores, sorted by suitability (highest first)
        """
        scored_tenders = []

        for tender in tenders:
            result = self.score_tender(tender, sme_profile)
            tender_with_score = {
                **tender,
                "sme_score": result.overall_score,
                "sme_analysis": {
                    "score_breakdown": result.category_scores,
                    "recommendations": result.recommendations,
                    "risk_factors": result.risk_factors,
                    "confidence": result.confidence
                }
            }
            scored_tenders.append(tender_with_score)

        # Sort by score (highest first)
        scored_tenders.sort(key=lambda x: x["sme_score"], reverse=True)

        return scored_tenders


# Convenience function for single tender scoring
def score_tender_for_sme(
    tender_data: Dict[str, Any],
    company_size: str = "small",
    annual_turnover: Optional[float] = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Quick function to score a single tender for SME suitability.

    Args:
        tender_data: Tender information
        company_size: "micro", "small", or "medium"
        annual_turnover: Optional annual turnover in EUR

    Returns:
        Tuple of (score, analysis_dict)
    """
    size_map = {
        "micro": SMECategory.MICRO,
        "small": SMECategory.SMALL,
        "medium": SMECategory.MEDIUM
    }

    profile = SMEProfile(
        size=size_map.get(company_size, SMECategory.SMALL),
        annual_turnover=annual_turnover
    )

    scorer = SMEScorer()
    analysis = scorer.get_sme_analysis(tender_data, profile)

    return analysis["sme_suitability_score"], analysis
