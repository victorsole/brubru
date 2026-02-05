"""
Delegation Predictor - Phase 3.2

Predicts when national delegations deviate from their group's position.

Factors:
- National interest (agriculture for FR, industry for DE, etc.)
- Governing vs opposition status
- Historical deviation patterns
- Section splits (Greens vs EFA, ALDE vs EDP)

Usage:
    predictor = DelegationPredictor()
    deviations = await predictor.predict_deviations("EPP", "2024/0138(COD)")
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session

from core.database import SessionLocal
from .cohesion_analyzer import CohesionAnalyzer

logger = logging.getLogger(__name__)


class DeviationRisk(str, Enum):
    """Risk level for delegation deviation."""
    LOW = "low"  # < 20% chance
    MODERATE = "moderate"  # 20-40%
    HIGH = "high"  # 40-60%
    VERY_HIGH = "very_high"  # > 60%


@dataclass
class DelegationDeviation:
    """Prediction of delegation deviation from group line."""
    country_code: str
    country_name: str
    group_code: str
    deviation_risk: DeviationRisk
    deviation_probability: float
    likely_direction: str  # 'more_supportive', 'more_opposed', 'abstain'

    # Factors
    national_interest_factor: float  # 0-1, how much this affects their country
    governing_status: str  # 'governing', 'opposition', 'mixed'
    historical_deviation_rate: float

    # Key reasons
    reasons: List[str] = field(default_factory=list)


@dataclass
class SectionSplit:
    """Prediction of section split within a group."""
    group_code: str
    section_name: str  # e.g., 'Greens', 'EFA', 'ALDE', 'EDP'
    split_probability: float
    expected_position: str  # 'FOR', 'AGAINST', 'ABSTENTION'
    seats: int

    # Factors
    historical_split_rate: float
    policy_alignment: float  # How aligned this section is with vote topic


@dataclass
class DelegationAnalysis:
    """Full delegation analysis for a procedure."""
    procedure_ref: str
    group_code: str
    expected_group_position: str

    # Delegation deviations
    deviations: List[DelegationDeviation] = field(default_factory=list)

    # Section splits (for Greens/EFA and Renew)
    section_splits: List[SectionSplit] = field(default_factory=list)

    # Summary
    total_deviation_risk: float = 0.0
    at_risk_seats: int = 0


class DelegationPredictor:
    """
    Predicts delegation deviations and section splits.

    Uses national interest factors and historical patterns.
    """

    # Country names
    COUNTRY_NAMES = {
        'DE': 'Germany', 'FR': 'France', 'IT': 'Italy', 'ES': 'Spain',
        'PL': 'Poland', 'RO': 'Romania', 'NL': 'Netherlands', 'BE': 'Belgium',
        'GR': 'Greece', 'CZ': 'Czechia', 'PT': 'Portugal', 'SE': 'Sweden',
        'HU': 'Hungary', 'AT': 'Austria', 'BG': 'Bulgaria', 'DK': 'Denmark',
        'FI': 'Finland', 'SK': 'Slovakia', 'IE': 'Ireland', 'HR': 'Croatia',
        'LT': 'Lithuania', 'SI': 'Slovenia', 'LV': 'Latvia', 'EE': 'Estonia',
        'CY': 'Cyprus', 'LU': 'Luxembourg', 'MT': 'Malta',
    }

    # National interest sensitivities by policy area
    # Higher = more likely to deviate on this topic
    NATIONAL_INTERESTS = {
        'DE': {'industry': 0.8, 'automotive': 0.9, 'energy': 0.7, 'fiscal': 0.8},
        'FR': {'agriculture': 0.9, 'culture': 0.8, 'nuclear': 0.9, 'defense': 0.7},
        'IT': {'migration': 0.8, 'fiscal': 0.7, 'agriculture': 0.6},
        'ES': {'agriculture': 0.7, 'fisheries': 0.8, 'tourism': 0.6},
        'PL': {'coal': 0.9, 'agriculture': 0.7, 'rule_of_law': 0.9, 'migration': 0.7},
        'NL': {'fiscal': 0.8, 'trade': 0.7, 'agriculture': 0.6},
        'BE': {'trade': 0.6, 'institutional': 0.5},
        'GR': {'migration': 0.8, 'fiscal': 0.7, 'tourism': 0.6},
        'HU': {'rule_of_law': 0.9, 'migration': 0.9, 'agriculture': 0.6},
        'CZ': {'automotive': 0.7, 'energy': 0.6},
        'PT': {'fisheries': 0.7, 'cohesion': 0.6},
        'SE': {'environment': 0.7, 'trade': 0.6},
        'AT': {'transit': 0.7, 'migration': 0.6},
        'IE': {'corporate_tax': 0.9, 'trade': 0.7},
        'DK': {'fisheries': 0.7, 'opt_outs': 0.8},
        'FI': {'forestry': 0.8, 'defense': 0.6},
    }

    # Committee to policy area mapping
    COMMITTEE_POLICY = {
        'AGRI': 'agriculture',
        'PECH': 'fisheries',
        'ITRE': 'industry',
        'ENVI': 'environment',
        'ECON': 'fiscal',
        'INTA': 'trade',
        'LIBE': 'migration',
        'TRAN': 'transport',
        'CULT': 'culture',
        'AFET': 'defense',
    }

    # Section compositions within groups
    GROUP_SECTIONS = {
        'Greens/EFA': {
            'Greens': {
                'seats': 38,
                'bias': {'environment': 0.9, 'social': 0.7, 'fiscal': 0.3}
            },
            'EFA': {
                'seats': 15,
                'bias': {'regional': 0.9, 'culture': 0.8, 'environment': 0.5}
            }
        },
        'Renew': {
            'ALDE': {
                'seats': 60,
                'bias': {'trade': 0.8, 'fiscal': 0.7, 'social': 0.5}
            },
            'EDP': {
                'seats': 17,
                'bias': {'regional': 0.7, 'agriculture': 0.6, 'social': 0.6}
            }
        }
    }

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._owns_db = db is None
        self._cohesion_analyzer = None

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

    def _get_policy_area(self, lead_committee: Optional[str]) -> Optional[str]:
        """Map committee to policy area."""
        if not lead_committee:
            return None
        return self.COMMITTEE_POLICY.get(lead_committee)

    def _get_national_interest_factor(
        self,
        country_code: str,
        policy_area: Optional[str]
    ) -> float:
        """Get how sensitive a country is to a policy area."""
        if not policy_area:
            return 0.0

        country_interests = self.NATIONAL_INTERESTS.get(country_code, {})
        return country_interests.get(policy_area, 0.0)

    def _get_governing_status(
        self,
        country_code: str,
        group_code: str
    ) -> str:
        """
        Determine if the delegation's parties are in government.

        This would normally query the governing_parties table.
        Returns simplified status for now.
        """
        # Simplified - would query database for actual status
        # EPP governments: DE (partial), IT, GR, HR, CY, etc.
        # S&D governments: ES, PT, DK, MT
        # This is illustrative - real implementation would query governing_parties.csv

        epp_gov = ['GR', 'HR', 'CY', 'RO', 'LT', 'LV']
        sd_gov = ['ES', 'PT', 'DK', 'MT', 'DE']
        renew_gov = ['EE', 'NL', 'BE']

        if group_code == 'EPP' and country_code in epp_gov:
            return 'governing'
        elif group_code == 'S&D' and country_code in sd_gov:
            return 'governing'
        elif group_code == 'Renew' and country_code in renew_gov:
            return 'governing'

        # Check for grand coalitions
        grand_coalition = ['DE', 'AT', 'NL', 'BE']
        if country_code in grand_coalition:
            return 'mixed'

        return 'opposition'

    def _calculate_deviation_risk(
        self,
        national_interest: float,
        governing_status: str,
        historical_rate: float = 0.15
    ) -> Tuple[DeviationRisk, float]:
        """Calculate deviation risk and probability."""
        # Base probability from historical rate
        prob = historical_rate

        # Adjust for national interest
        prob += national_interest * 0.3

        # Adjust for governing status (governing parties more likely to follow EU consensus)
        if governing_status == 'governing':
            prob *= 0.7
        elif governing_status == 'opposition':
            prob *= 1.3

        # Cap probability
        prob = min(0.9, max(0.05, prob))

        # Determine risk level
        if prob < 0.20:
            risk = DeviationRisk.LOW
        elif prob < 0.40:
            risk = DeviationRisk.MODERATE
        elif prob < 0.60:
            risk = DeviationRisk.HIGH
        else:
            risk = DeviationRisk.VERY_HIGH

        return risk, prob

    async def predict_deviations(
        self,
        group_code: str,
        procedure_ref: str,
        lead_committee: Optional[str] = None,
        expected_position: str = "FOR"
    ) -> List[DelegationDeviation]:
        """
        Predict which delegations might deviate from the group line.

        Args:
            group_code: EP group code
            procedure_ref: OEIL procedure reference
            lead_committee: Lead committee code
            expected_position: Expected group position

        Returns:
            List of DelegationDeviation predictions
        """
        policy_area = self._get_policy_area(lead_committee)
        deviations = []

        # Get group's delegations (simplified - would query database)
        # For now, check major countries
        major_countries = ['DE', 'FR', 'IT', 'ES', 'PL', 'NL', 'BE', 'GR', 'HU', 'CZ']

        for country_code in major_countries:
            national_interest = self._get_national_interest_factor(country_code, policy_area)
            governing_status = self._get_governing_status(country_code, group_code)

            # Skip if no significant national interest
            if national_interest < 0.5:
                continue

            risk, prob = self._calculate_deviation_risk(
                national_interest=national_interest,
                governing_status=governing_status
            )

            # Determine likely direction of deviation
            if expected_position == 'FOR':
                likely_direction = 'more_opposed' if national_interest > 0.7 else 'abstain'
            else:
                likely_direction = 'more_supportive' if national_interest > 0.7 else 'abstain'

            # Build reasons list
            reasons = []
            if national_interest > 0.6:
                reasons.append(f"High national interest in {policy_area}")
            if governing_status == 'opposition':
                reasons.append("Delegation parties in opposition")
            elif governing_status == 'mixed':
                reasons.append("Mixed governing/opposition status")

            deviations.append(DelegationDeviation(
                country_code=country_code,
                country_name=self.COUNTRY_NAMES.get(country_code, country_code),
                group_code=group_code,
                deviation_risk=risk,
                deviation_probability=prob,
                likely_direction=likely_direction,
                national_interest_factor=national_interest,
                governing_status=governing_status,
                historical_deviation_rate=0.15,  # Would be calculated from data
                reasons=reasons
            ))

        # Sort by deviation probability
        deviations.sort(key=lambda x: x.deviation_probability, reverse=True)

        return deviations

    async def predict_section_splits(
        self,
        group_code: str,
        lead_committee: Optional[str] = None
    ) -> List[SectionSplit]:
        """
        Predict section splits within Greens/EFA or Renew.

        Args:
            group_code: Must be 'Greens/EFA' or 'Renew'
            lead_committee: Lead committee code

        Returns:
            List of SectionSplit predictions
        """
        if group_code not in self.GROUP_SECTIONS:
            return []

        policy_area = self._get_policy_area(lead_committee)
        sections = self.GROUP_SECTIONS[group_code]
        splits = []

        for section_name, section_data in sections.items():
            seats = section_data['seats']
            bias = section_data['bias']

            # Calculate policy alignment
            policy_alignment = bias.get(policy_area, 0.3) if policy_area else 0.5

            # Calculate split probability
            # Higher alignment = more unified, lower = more likely to deviate
            split_prob = 1.0 - policy_alignment

            # Historical split rates (would be calculated from data)
            historical_rate = 0.15 if group_code == 'Greens/EFA' else 0.10

            # Adjust for historical patterns
            split_prob = split_prob * 0.7 + historical_rate * 0.3

            # Determine expected position based on policy alignment
            if policy_alignment > 0.6:
                expected_pos = 'FOR'
            elif policy_alignment < 0.4:
                expected_pos = 'AGAINST'
            else:
                expected_pos = 'ABSTENTION'

            splits.append(SectionSplit(
                group_code=group_code,
                section_name=section_name,
                split_probability=split_prob,
                expected_position=expected_pos,
                seats=seats,
                historical_split_rate=historical_rate,
                policy_alignment=policy_alignment
            ))

        return splits

    async def analyze_delegations(
        self,
        procedure_ref: str,
        group_code: str,
        lead_committee: Optional[str] = None,
        expected_group_position: str = "FOR"
    ) -> DelegationAnalysis:
        """
        Full delegation analysis for a procedure.

        Returns deviations and section splits.
        """
        deviations = await self.predict_deviations(
            group_code=group_code,
            procedure_ref=procedure_ref,
            lead_committee=lead_committee,
            expected_position=expected_group_position
        )

        section_splits = await self.predict_section_splits(
            group_code=group_code,
            lead_committee=lead_committee
        )

        # Calculate summary stats
        total_risk = sum(d.deviation_probability for d in deviations) / max(len(deviations), 1)

        # Estimate at-risk seats (simplified)
        at_risk = sum(
            10 if d.deviation_risk in (DeviationRisk.HIGH, DeviationRisk.VERY_HIGH) else 0
            for d in deviations
        )

        return DelegationAnalysis(
            procedure_ref=procedure_ref,
            group_code=group_code,
            expected_group_position=expected_group_position,
            deviations=deviations,
            section_splits=section_splits,
            total_deviation_risk=total_risk,
            at_risk_seats=at_risk
        )


# Singleton instance
_predictor_instance: Optional[DelegationPredictor] = None


def get_delegation_predictor() -> DelegationPredictor:
    """Get or create the delegation predictor instance."""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = DelegationPredictor()
    return _predictor_instance
